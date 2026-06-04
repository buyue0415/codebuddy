#!/usr/bin/env python
"""Comprehensive Test Runner — Stock Investment Management System.

Usage:
    python tests/run_all.py                    # Run all unit tests
    python tests/run_all.py --integration      # Run unit + API integration tests
    python tests/run_all.py --module=db        # Run specific module only
    python tests/run_all.py --list             # List all modules

Modules:
    db         - Database CRUD layer (P1 CRITICAL)
    sync       - Sync engine / signals (P1 CRITICAL)
    news       - News fetcher (P1 CRITICAL)
    api        - API server routing & format (P1 CRITICAL)
    dal        - DB schema & integrity (P1 CRITICAL)
    integrity  - Cross-table data integrity (P1 CRITICAL)
    stmt       - Statement parser (P2 HIGH)
    learn      - Self-learning params structure (P2 HIGH)
    update     - Daily sync pipeline (P2 HIGH)
    sched      - Scheduler & automation (P2 HIGH)
    stkdb      - Stock code & watchlist (P2 HIGH)
    optimize   - ML prediction optimization (P2 HIGH)
    compat     - Expert report compatibility (P2 HIGH)
    api_it     - API integration (P2 HIGH) — requires server running
"""
import os, sys, argparse, time, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tests'))

from conftest import print_header

# ======================================================================
# Module registry
# ======================================================================

MODULES = {
    'db':      {'path': 'tests.test_db_helper',           'priority': 'P1 CRITICAL', 'desc': 'Database CRUD layer'},
    'sync':    {'path': 'tests.test_sync_engine',          'priority': 'P1 CRITICAL', 'desc': 'Signals / predictions / EMA'},
    'news':    {'path': 'tests.test_news_fetcher',         'priority': 'P1 CRITICAL', 'desc': 'News parsing / sentiment'},
    'api':     {'path': 'tests.test_api_server',           'priority': 'P1 CRITICAL', 'desc': 'API server routing & format'},
    'dal':     {'path': 'tests.test_database_layer',       'priority': 'P1 CRITICAL', 'desc': 'DB schema & integrity'},
    'integrity': {'path': 'tests.test_data_integrity',     'priority': 'P1 CRITICAL', 'desc': 'Cross-table data integrity'},
    'stmt':    {'path': 'tests.test_statement_parser',     'priority': 'P2 HIGH',     'desc': 'Position calculation logic'},
    'learn':   {'path': 'tests.test_self_learning',        'priority': 'P2 HIGH',     'desc': 'Self-learning params structure'},
    'update':  {'path': 'tests.test_daily_update',         'priority': 'P2 HIGH',     'desc': 'Daily sync pipeline'},
    'sched':   {'path': 'tests.test_scheduler',            'priority': 'P2 HIGH',     'desc': 'Scheduler & automation'},
    'stkdb':   {'path': 'tests.test_stock_database',       'priority': 'P2 HIGH',     'desc': 'Stock code & watchlist'},
    'optimize': {'path': 'tests.test_optimize_predict',    'priority': 'P2 HIGH',     'desc': 'ML prediction optimization'},
    'compat':  {'path': 'tests.test_report_compatibility', 'priority': 'P2 HIGH',     'desc': 'Expert report compatibility'},
}


def run_module(module_name, verbosity=2):
    """Run a single test module and return results."""
    suite = unittest.defaultTestLoader.loadTestsFromName(MODULES[module_name]['path'])
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return result


def run_integration_tests():
    """Run the API-based integration test (requires server on :8766)."""
    print_header("API Integration Tests (requires server on localhost:8766)")
    
    # Check if server is running
    import urllib.request
    try:
        resp = urllib.request.urlopen("http://localhost:8766/api/v2/init", timeout=3)
        print("  Server: ONLINE\n")
    except Exception as e:
        print(f"  SERVER OFFLINE: {e}")
        print("  Start server_v2.py first, then re-run with --integration\n")
        return None

    # Run the existing integration test suite
    int_test_path = os.path.join(ROOT, 'scripts', 'run_tests.py')
    if os.path.exists(int_test_path):
        result = os.system(f'"{sys.executable}" "{int_test_path}"')
        return result == 0
    return False


def main():
    parser = argparse.ArgumentParser(description='Stock System Test Suite')
    parser.add_argument('--module', '-m', choices=list(MODULES.keys()) + ['api'],
                        help='Run specific module only')
    parser.add_argument('--integration', '-i', action='store_true',
                        help='Include API integration tests')
    parser.add_argument('--verbosity', '-v', type=int, default=2,
                        help='Test verbosity (1=minimal, 2=detailed)')
    parser.add_argument('--list', action='store_true',
                        help='List all available test modules')
    args = parser.parse_args()

    if args.list:
        print_header("Available Test Modules")
        print(f"{'Module':<10} {'Priority':<15} {'Description':<40}")
        print("-" * 65)
        for name, info in MODULES.items():
            print(f"{name:<10} {info['priority']:<15} {info['desc']:<40}")
        print("api       P2 HIGH         API integration (server required)")
        return

    start_time = time.time()
    all_passed = True
    total_tests = 0
    total_failures = 0
    total_errors = 0

    if args.module:
        # Run specific module
        if args.module == 'api':
            ok = run_integration_tests()
            if ok is None:
                sys.exit(2)
            sys.exit(0 if ok else 1)
        
        print_header(f"Module: {args.module} ({MODULES[args.module]['desc']})")
        result = run_module(args.module, args.verbosity)
        if not result.wasSuccessful():
            all_passed = False
        total_tests += result.testsRun
    else:
        # Run all unit test modules (P1 first, then P2)
        for priority_name, modules in [('P1 CRITICAL', ['db', 'sync', 'news', 'api', 'dal', 'integrity']),
                                        ('P2 HIGH', ['stmt', 'learn', 'update', 'sched', 'stkdb', 'optimize', 'compat'])]:
            print_header(f"Priority: {priority_name}")
            for mod in modules:
                print(f"  >>> Running {mod} ({MODULES[mod]['desc']})...\n")
                result = run_module(mod, args.verbosity)
                if not result.wasSuccessful():
                    all_passed = False
                total_tests += result.testsRun
                print()

        # Optionally run integration tests
        if args.integration:
            print()
            ok = run_integration_tests()
            if ok is None:
                # Server not running — not a failure, just skip
                print("  [SKIP] Integration tests (server offline)")
            elif not ok:
                all_passed = False

    # Summary
    elapsed = time.time() - start_time
    print_header("Test Suite Summary")
    status = "ALL PASSED" if all_passed else "SOME FAILURES"
    print(f"  Status:     {status}")
    print(f"  Duration:   {elapsed:.1f}s")
    print(f"  Tests run:  {total_tests}")
    print()

    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
