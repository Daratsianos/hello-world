.PHONY: help demo demo-approve

help:
	@echo "Targets:"
	@echo "  make demo         # run planner in preview mode"
	@echo "  make demo-approve # run planner with --approve-all"

demo:
	python3 prototype/unsubscribe_planner.py \
	  --input prototype/sample_messages.json \
	  --allowlist prototype/allowlist.txt \
	  --denylist prototype/denylist.txt

demo-approve:
	python3 prototype/unsubscribe_planner.py \
	  --input prototype/sample_messages.json \
	  --allowlist prototype/allowlist.txt \
	  --denylist prototype/denylist.txt \
	  --approve-all
