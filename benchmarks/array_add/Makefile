bench: benchpy benchspy

benchpy:
	python bench_numpy.py

benchspy:
	spy build --release bench.spy
	./build/bench

clean:
	rm -rf build
