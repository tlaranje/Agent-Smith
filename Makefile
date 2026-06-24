RM		:= rm -rf
FIND	:= find

install:
	@clear && uv sync

run:
	@clear && uv run python -m student

debug:
	@clear && uv run python -m pdb -m student

clean:
	@clear
	@echo "Cleaning project cache..."
	@$(FIND) . -type d -name "__pycache__" -exec $(RM) {} +
	@$(FIND) . -type d -name ".mypy_cache" -exec $(RM) {} +
	@$(FIND) . -type d -name ".pytest_cache" -exec $(RM) {} +
	@$(FIND) . -type f -name "*.pyc" -delete
	@$(FIND) . -type f -name "*.pyo" -delete
	@$(RM) .venv
	@$(RM) Agent_Smith.egg-info
	@$(RM) .community.db

lint:
	@clear && uv run flake8 student
	@uv run mypy student --warn-return-any \
		--warn-unused-ignores \
	    --ignore-missing-imports \
	    --disallow-untyped-defs \
	    --check-untyped-defs

lint-strict:
	@clear && uv run flake8 student
	@uv run mypy student --strict

.PHONY: install run debug clean build build-clean lint lint-strict