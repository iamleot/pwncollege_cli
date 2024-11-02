.POSIX:

BLACK = black
FLAKE8 = flake8
MYPY = mypy
PYTHON = python3

all:

lint: black flake8 mypy

black:
	@$(BLACK) --check .

flake8:
	@$(FLAKE8) --select=E9,F63,F7,F82 --show-source .
	@$(FLAKE8) --exit-zero --max-complexity=10 .
	
mypy:
	@$(MYPY) --strict --exclude tests .

test:
	$(PYTHON) -m unittest discover -s tests -v
