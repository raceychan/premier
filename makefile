test:
	uv run pytest -sv 
	
report:
	uv run pytest -sv --cov-report term-missing --cov=premier tests/

switch:
	git switch -c dev