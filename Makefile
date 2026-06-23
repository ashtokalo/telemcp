PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: configure auth auth-phone auth-qr test connection

configure:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]" -q

auth-phone:
	$(PYTHON) -m telemcp.auth $(ARGS)

auth-qr:
	$(PYTHON) -m telemcp.auth --qr $(ARGS)

test:
	$(PYTHON) -m pytest tests/ -v

connection:
	$(PYTHON) -m telemcp.test_connection $(ARGS)
