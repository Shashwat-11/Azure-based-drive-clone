"""
Benchmark and load testing scripts for the Drive platform.

Usage:
    python -m tests.benchmarks.upload_bench
    python -m tests.benchmarks.search_bench
    python -m tests.benchmarks.permission_bench

Load testing (requires locust):
    locust -f tests/benchmarks/locustfile.py --host=http://localhost:8000

NOTE: All benchmark results must be collected against a running instance
with representative data volumes. These scripts provide the measurement
framework but do not include pre-recorded benchmark numbers.
"""
