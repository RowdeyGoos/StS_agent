"""Compare identical inert inputs through separately compiled v3/v4 reward binders."""
import argparse
import json
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dotnet', required=True)
    parser.add_argument('--baseline-dll', required=True)
    parser.add_argument('--candidate-dll', required=True)
    args = parser.parse_args()
    results = []
    for path in (args.baseline_dll, args.candidate_dll):
        result = subprocess.run([args.dotnet, path, '--trace'], capture_output=True, timeout=30)
        if result.returncode or result.stderr or len(result.stdout) > 262144:
            raise AssertionError('inert trace process failed')
        results.append(json.loads(result.stdout))
    assert len(results[0]) == 14 and results[0] == results[1], 'frozen v3 and v4 observable traces differ'
    print(json.dumps({'status': 'passed', 'trace_scenarios': len(results[0]),
                      'same_getter_order_and_counts': True, 'same_outcomes_and_candidate_snapshots': True}, separators=(',', ':')))


if __name__ == '__main__':
    main()
