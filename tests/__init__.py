"""Stock Investment Management System - Automated Test Suite

Test hierarchy (priority order):
  P1 [CRITICAL]  test_db_helper     - Database CRUD layer (18 query functions)
  P1 [CRITICAL]  test_sync_engine   - calc_signals, gen_pred, _ema, _new_lp
  P1 [CRITICAL]  test_news_fetcher  - _parse_news_table, _detect_sentiment, _is_major
  P2 [HIGH]      test_statement_parser - Position calculation from trades
  P2 [HIGH]      test_audit_system  - SQLite-based audit output structure
  P3 [MEDIUM]    test_reinject      - HTML data injection verification
"""
