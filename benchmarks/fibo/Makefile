all: benchjulia benchcodoninterp benchcodon benchpy benchpypy benchspy

check-ci: benchjulia benchcodoninterp benchcodon benchpypy benchspy
test: benchspy

benchjulia:
	@julia --version
	julia -O3 fib.jl

benchcodoninterp:
	@echo -n "Codon " && codon --version
	codon run --release fib.codon

benchcodon:
	@echo -n "Codon " && codon --version
	@mkdir -p build/codon
	codon build --release fib.codon && mv fib build/codon
	./build/codon/fib

benchpy:
	@python --version
	python fib.py

benchpypy:
	@$$(uv python find pypy --no-project) --version
	$$(uv python find pypy --no-project) fib.py

benchspy:
	spy build --release fib.spy
	./build/fib
