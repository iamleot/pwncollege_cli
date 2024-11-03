.POSIX:

BLACK = black
FLAKE8 = flake8
MYPY = mypy
PYTEST = pytest
PYTHON = python3

all:

lint: black flake8 mypy

black:
	@$(BLACK) --check .

flake8:
	@$(FLAKE8) --select=E9,F63,F7,F82 --show-source .
	@$(FLAKE8) --exit-zero --max-complexity=10 .
	
mypy-install-types:
	@$(MYPY) --non-interactive --install-types .

mypy:
	@$(MYPY) --strict --exclude tests .

test:
	$(PYTEST) -v
