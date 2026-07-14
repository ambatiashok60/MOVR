1. Inspect existing GENERATE_TC worker and final completion publisher.
2. Trace the exact functional persistence and final result construction.
3. Add api_test_gen request normalisation in the controller.
4. Ensure the flag survives queue serialization/deserialization.
5. Add API/functional routing in the generation service or worker.
6. Create API Pydantic output models.
7. Create the API output parser.
8. Create API repository discovery.
9. Create API prompt builders.
10. Create run_api_tc_gen_agent().
11. Add _try_agentic_api_generation() to TestCaseService.
12. Integrate API persistence.
13. Reuse the existing COMPLETED event builder.
14. Add cancellation and failure handling.
15. Add unit and integration tests.
16. Run existing functional regression tests.
17. Produce a change report with created and modified files.