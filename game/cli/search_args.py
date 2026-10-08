"""Shared explicit search configuration for existing installed commands."""


def add_search_arguments(parser, *, collection=False, method_switch=True):
    parser.add_argument('--search', action='store_true', help='Enable experimental public-only combat search')
    parser.add_argument('--search-simulations', type=int, default=16 if collection else 64)
    parser.add_argument('--search-seconds', type=float, default=5., help='Per-action thinking ceiling, separate from episode --time-limit')
    parser.add_argument('--search-depth', type=int, default=64)
    parser.add_argument('--search-leaf-rollout-steps', type=int, default=0,
                        help='Greedy public-observation actions before leaf evaluation; zero uses the critic directly')
    parser.add_argument('--search-q-scale', type=float, default=.1,
                        help='Experimental value weight in allocation and policy targets; default 0.1')
    parser.add_argument('--search-final-selection', choices=('prior_value', 'max_value'), default='prior_value',
                        help='Final choice among evaluated contenders; max_value leaves allocation and targets unchanged')
    parser.add_argument('--search-seed', type=int, default=0, help='Planner RNG, independent of the game seed')
    parser.add_argument('--search-model', choices=('reconstruction_v1', 'public_belief_v1', 'direct_belief_v1'),
                        default='reconstruction_v1', help='Belief modes require declared controlled starts; direct_belief_v1 supports a guarded content slice')
    parser.add_argument('--belief-particles', type=int, default=4)
    parser.add_argument('--belief-proposals', type=int, default=1024)
    parser.add_argument('--belief-replay-proposals', type=int, default=2048)
    parser.add_argument('--belief-replay-steps', type=int, default=16384)
    parser.add_argument('--belief-seconds', type=float, default=5., help='Per-update belief ceiling, including recovery')
    if method_switch:
        parser.add_argument('--search-method', choices=('gumbel', 'root'), default='gumbel')
    else:
        parser.set_defaults(search_method='gumbel')


def search_config(args, *, collection=False):
    if not args.search:
        return None
    from game.agent.search import SearchConfig
    return SearchConfig(simulations=args.search_simulations, max_depth=args.search_depth,
                        time_limit=args.search_seconds, seed=args.search_seed,
                        method=args.search_method, exploration=collection, model_version=args.search_model,
                        belief_particles=args.belief_particles, belief_proposals=args.belief_proposals,
                        belief_replay_proposals=args.belief_replay_proposals,
                        belief_replay_steps=args.belief_replay_steps, belief_seconds=args.belief_seconds,
                        leaf_rollout_steps=args.search_leaf_rollout_steps,
                        q_scale=args.search_q_scale, final_selection=args.search_final_selection)
