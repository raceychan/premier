test:
	pixi run --environment test pytest -sv --cov-report term-missing --cov=premier tests/

switch:
	git switch -c dev