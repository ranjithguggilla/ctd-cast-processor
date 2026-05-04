.PHONY: install dev lint test test-cov sample process clean help

PYTHON  := python3
PIP     := pip
PYTEST  := pytest

help:
	@echo "CTD Cast Processor — available targets:"
	@echo ""
	@echo "  install      Install package (production)"
	@echo "  dev          Install package with dev extras"
	@echo "  lint         Run ruff linter"
	@echo "  test         Run full test suite"
	@echo "  test-cov     Run tests with coverage report"
	@echo "  sample       Generate synthetic sample CNV files"
	@echo "  process      Batch-process sample_data/raw/ → output/"
	@echo "  clean        Remove build artefacts and cache"

install:
	$(PIP) install -e .

dev:
	$(PIP) install -e ".[dev]"

lint:
	ruff check ctd_processor/ tests/

test:
	$(PYTEST) -v --tb=short tests/

test-cov:
	$(PYTEST) --cov=ctd_processor --cov-report=term-missing --cov-report=html tests/
	@echo "HTML report: htmlcov/index.html"

sample:
	$(PYTHON) sample_data/generate_sample_cnv.py

process: sample
	ctd-processor batch sample_data/raw/ --output output/

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
