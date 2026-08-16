# Prototype

Python standard library only.

Run API:

```bash
python3 prototype/mxis_ai_api_server.py --host 127.0.0.1 --port 8765
```

Validate:

```bash
python3 prototype/mxis_feature_extractor.py --validate tests/fixtures/feature-extractor-cases.json --pretty
python3 prototype/mxis_rule_evaluator.py --validate tests/fixtures/rule-evaluator-cases.json --pretty
python3 prototype/mxis_synthetic_dataset_generator.py --pretty
```

The Python code is a reference implementation for Java backend porting, not the final production backend.

