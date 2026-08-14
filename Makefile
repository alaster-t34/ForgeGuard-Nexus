.PHONY: run test edge jetson-preflight openeval benchmark external-cwru fault-campaign visual-dry-run package

run:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	PYTHONPATH=backend:edge-node pytest -q backend/tests edge-node/tests

edge:
	PYTHONPATH=edge-node python -m forgeguard_edge.cli inspect simulator/sample_vibration.csv

jetson-preflight:
	PYTHONPATH=edge-node python -m forgeguard_edge.cli jetson-preflight

openeval:
	PYTHONPATH=backend python scripts/build_openeval.py

benchmark:
	PYTHONPATH=backend python scripts/run_benchmarks.py --without-cnn

external-cwru:
	PYTHONPATH=backend python scripts/run_external_benchmark.py cwru data/external/cwru

fault-campaign:
	PYTHONPATH=backend python scripts/run_fault_campaign.py

visual-dry-run:
	python scripts/run_visual_benchmark.py --dry-run

package:
	python scripts/package_release.py
