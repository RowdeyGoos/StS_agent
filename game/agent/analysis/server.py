"""Loopback-only read-only viewer over one export and explicit inference bundles."""
from functools import lru_cache
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import math
from pathlib import Path
import re
import threading
from urllib.parse import parse_qs, urlsplit

from game.agent.action_policy import action_mask
from game.agent.contracts import full as f
from game.agent.training.rewards import strict_json
from .decisions import detail, json_bytes, state_digest
from .report import CHUNK_SIZE, SCHEMA
from .sources import identity, read_json, text


class AnalysisStore:
    def __init__(self, directory, checkpoints=()):
        self.directory = Path(directory).resolve()
        self.report = read_json(self.directory/'report.json')
        if self.report.get('schema') != SCHEMA or self.report.get('chunk_size') != CHUNK_SIZE:
            raise ValueError('Unsupported analysis export')
        self.runs = {}
        for row in self.report['runs']:
            key = identity(row['id'])
            if (key in self.runs or type(row['steps']) is not int or row['steps'] < 0
                    or len(row['chunks']) != math.ceil(row['steps']/CHUNK_SIZE)
                    or any(type(v) is not str or not re.fullmatch('[0-9a-f]{64}', v) for v in row['chunks'])):
                raise ValueError('Invalid exported run index')
            self.runs[key] = row
        self.models, self.model_info = {}, []
        self.inference_lock = threading.Lock()
        if len(checkpoints) > 4:
            raise ValueError('Compare at most four explicit checkpoints')
        if checkpoints:
            try:
                import torch
                from game.agent.training.checkpoint import load_policy
                from game.agent.training.rollout import fingerprint
            except ModuleNotFoundError as error:
                raise ModuleNotFoundError('Checkpoint comparison requires sts-agent[train]') from error
            torch.set_num_threads(1)
            for label, path in checkpoints:
                text(label, 'checkpoint label')
                if label in self.models:
                    raise ValueError('Duplicate checkpoint label')
                policy = load_policy(path)
                self.models[label] = policy
                self.model_info.append({'label': label, 'identity': policy.identity,
                                        'behavior': fingerprint(policy.model),
                                        'action_policy': policy.model.action_policy,
                                        'reward_spec': policy.reward_spec.to_dict(),
                                        'reward_identity': policy.reward_spec.identity})

    def overview(self):
        return {**self.report, 'models': self.model_info,
                'runs': [{k: v for k, v in row.items() if k not in ('timeline', 'rooms', 'chunks', 'flags')}
                         | {'flag_counts': {level: sum(f['level']==level for f in row['flags'])
                                           for level in ('warning', 'info')}} for row in self.runs.values()]}

    def run(self, key):
        identity(key)
        if key not in self.runs:
            raise ValueError('Unknown run')
        return {k: v for k, v in self.runs[key].items() if k != 'chunks'}

    @lru_cache(maxsize=2)
    def _chunk(self, key, chunk):
        path = self.directory/'decisions'/f'{key}-{chunk}.json.gz'
        if path.is_symlink() or path.parent.is_symlink() or path.stat().st_size > 32*1024*1024:
            raise ValueError('Invalid decision chunk')
        compressed = path.read_bytes()
        if hashlib.sha256(compressed).hexdigest() != self.runs[key]['chunks'][chunk]:
            raise ValueError('Decision chunk digest mismatch; rebuild the export')
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source:
            data = source.read(64*1024*1024+1)
        if len(data) > 64*1024*1024:
            raise ValueError('Oversized decision chunk')
        values = strict_json(data)
        if type(values) is not list or len(values) != min(CHUNK_SIZE, self.runs[key]['steps']-chunk*CHUNK_SIZE):
            raise ValueError('Malformed decision chunk')
        return values

    def decision(self, key, step):
        self.run(key)
        if type(step) is not int or not 0 <= step < self.runs[key]['steps']:
            raise ValueError('Decision index outside recording')
        value = self._chunk(key, step//CHUNK_SIZE)[step % CHUNK_SIZE]
        if value['step'] != step:
            raise ValueError('Decision index mismatch')
        return detail(value)

    def compare(self, key, step):
        value = self.decision(key, step)
        decision = f.from_dict(value['observation'])
        results = []
        # Inference is serialized so two browser tabs cannot race Torch settings.
        with self.inference_lock:
            for metadata in self.model_info:
                policy = self.models[metadata['label']]
                probabilities, critic = policy.probabilities(decision)
                allowed = action_mask(decision, policy.model.action_policy)
                if (set(probabilities) != {a.ref for a in decision.candidates}
                        or any(not math.isfinite(v) or not 0 <= v <= 1 for v in probabilities.values())
                        or not math.isclose(sum(probabilities.values()), 1., abs_tol=1e-5)
                        or not math.isfinite(critic)):
                    raise ValueError('Invalid checkpoint distribution')
                run = self.runs[key]
                same = (run['training']['behavior'] == metadata['behavior'] if run['training']
                        else run['metadata']['policy'] == policy.identity)
                results.append({**metadata, 'value': critic, 'matches_recorded_policy': same,
                                'probabilities': [{'ref': a.ref, 'probability': probabilities[a.ref],
                                                   'allowed': ok} for a, ok in zip(decision.candidates, allowed)]})
        return {'state_sha256': state_digest(decision), 'step': step, 'models': results,
                'interpretation': 'Recomputed preferences on one recorded public state. No alternative outcomes were simulated.'}


def make_server(store, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            port = self.server.server_port
            hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            if (self.headers.get('Host') not in hosts
                    or self.headers.get('Sec-Fetch-Site') == 'cross-site'
                    or self.headers.get('Origin') not in (None, *(f'http://{h}' for h in hosts))):
                self.send_error(403)
                return
            route = urlsplit(self.path)
            try:
                params = parse_qs(route.query, strict_parsing=True)
                if any(len(v) != 1 for v in params.values()):
                    raise ValueError('Duplicate query arguments')
                if route.path == '/api/report' and not params:
                    result = store.overview()
                elif route.path == '/api/run' and set(params) == {'id'}:
                    result = store.run(params['id'][0])
                elif route.path in ('/api/decision', '/api/compare') and set(params) == {'id', 'step'}:
                    if not re.fullmatch(r'0|[1-9][0-9]{0,6}', params['step'][0]):
                        raise ValueError('Invalid decision index')
                    method = store.compare if route.path.endswith('compare') else store.decision
                    result = method(params['id'][0], int(params['step'][0]))
                elif route.path in ('/', '/index.html', '/style.css', '/app.js') and not params:
                    filename = 'index.html' if route.path == '/' else route.path[1:]
                    path = store.directory/filename
                    if path.is_symlink():
                        raise ValueError('Unexpected asset symlink')
                    mime = {'index.html': 'text/html', 'style.css': 'text/css', 'app.js': 'text/javascript'}[filename]
                    self.respond(200, path.read_bytes(), mime)
                    return
                else:
                    self.respond(404, json_bytes({'error': 'Unknown resource'}))
                    return
                self.respond(200, json_bytes(result))
            except (ValueError, KeyError, TypeError, OSError, EOFError) as error:
                self.respond(400, json_bytes({'error': str(error)}))

        def respond(self, status, data, mime='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', mime+'; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
