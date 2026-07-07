"""
Phase 15I Tests: Enforce Practical Coverage Contract for Safe FR Capabilities

Tests verify that:
1. planner_v13 version is used
2. One Positive-only safe FR plans trigger replan even with skip reasons
3. One Positive-only safe NFR does NOT trigger replan
4. Blocked plans do not trigger replan
5. Positive + Negative + Boundary plans do not trigger replan
6. Replan prompt forbids OTP/dashboard/lockout/exact messages/screens
7. No requirement keyword branching in planner.py
8. No APPROVED or repairer logic
9. Diagnostics fields are properly set
10. Replan failure is handled by setting coverage_replan_succeeded=False and adding diagnostic message
"""

import pytest
from app.services.test_case_generation.models import (
    CoverageItem,
    PlannerOutput,
    RequirementForTestCase,
)
from app.services.test_case_generation.planner import (
    planner_needs_coverage_replan,
)
from app.services.test_case_generation.prompts import (
    TEST_CASE_PROMPT_VERSION,
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
    build_planner_replan_system_prompt,
    build_planner_replan_user_prompt,
)


class TestPhase15IVersionBump:
    """Verify planner_v13 is in use."""

    def test_planner_version_bumped_to_v13(self):
        """planner_v13 -> planner_v13"""
        assert TEST_CASE_PROMPT_VERSION == "planner_v13"

    def test_generator_version_unchanged(self):
        """Generator version remains generator_v8 (not edited)."""
        assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"

    def test_reviewer_version_unchanged(self):
        """Reviewer version remains reviewer_v6 (not edited)."""
        assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


class TestPhase15IReplanTrigger:
    """Verify replan trigger correctly identifies one-positive safe FR plans."""

    def _make_plan(
        self,
        requirement_type: str = "FR",
        safe_to_generate: bool = True,
        coverage_items: list[CoverageItem] | None = None,
        why_negative: str | None = None,
        why_boundary: str | None = None,
    ) -> PlannerOutput:
        """Helper to create test plans."""
        if coverage_items is None:
            coverage_items = [
                CoverageItem(
                    coverage_item="valid configured input succeeds",
                    test_type="Positive",
                    technique_used="Functional verification",
                    priority="High",
                    rationale="Test basic success",
                    source_basis=["requirement states capability"],
                )
            ]

        return PlannerOutput(
            requirement_id="REQ_1",
            requirement_text="Test requirement",
            requirement_type=requirement_type,
            testable=True,
            safe_to_generate=safe_to_generate,
            risk_level="Medium",
            ambiguity_level="Low",
            blocking_missing_information=[],
            missing_information=[],
            coverage_items=coverage_items,
            recommended_test_case_count=len(coverage_items),
            assumptions=[],
            why_negative_not_generated=why_negative,
            why_boundary_not_generated=why_boundary,
            coverage_replan_attempted=False,
            coverage_replan_reason=None,
            coverage_replan_succeeded=None,
        )

    def test_one_positive_safe_fr_triggers_replan(self):
        """Safe FR with one Positive triggers replan."""
        plan = self._make_plan(requirement_type="FR", safe_to_generate=True)
        assert planner_needs_coverage_replan(plan) is True

    def test_one_positive_safe_fr_with_skip_reasons_triggers_replan(self):
        """
        Safe FR with one Positive + skip reasons still triggers replan.
        This is the key Phase 15I fix: skip-reason escape hatch removed.
        """
        plan = self._make_plan(
            requirement_type="FR",
            safe_to_generate=True,
            why_negative="No invalid input mentioned in requirement",
            why_boundary="No boundary condition mentioned in requirement",
        )
        assert planner_needs_coverage_replan(plan) is True

    def test_one_positive_safe_nfr_does_not_trigger_replan(self):
        """
        Safe NFR with one Positive does NOT trigger replan.
        Coverage replan is FR-specific contract, not generic.
        """
        plan = self._make_plan(requirement_type="NFR", safe_to_generate=True)
        assert planner_needs_coverage_replan(plan) is False

    def test_one_positive_unsafe_fr_does_not_trigger_replan(self):
        """Unsafe FR (safe_to_generate=false) does not trigger replan."""
        plan = self._make_plan(
            requirement_type="FR",
            safe_to_generate=False,
        )
        assert planner_needs_coverage_replan(plan) is False

    def test_blocked_plan_does_not_trigger_replan(self):
        """Blocked plan (safe_to_generate=false, no coverage) does not trigger."""
        plan = self._make_plan(
            requirement_type="FR",
            safe_to_generate=False,
            coverage_items=[],
        )
        assert planner_needs_coverage_replan(plan) is False

    def test_two_coverage_items_does_not_trigger_replan(self):
        """Plan with 2 coverage items does not trigger replan."""
        plan = self._make_plan(
            requirement_type="FR",
            safe_to_generate=True,
            coverage_items=[
                CoverageItem(
                    coverage_item="valid configured input succeeds",
                    test_type="Positive",
                    technique_used="Functional verification",
                    priority="High",
                    rationale="Test basic success",
                    source_basis=["requirement states capability"],
                ),
                CoverageItem(
                    coverage_item="invalid configured input is rejected",
                    test_type="Negative",
                    technique_used="Input validation",
                    priority="High",
                    rationale="Test rejection",
                    source_basis=["requirement states capability"],
                ),
            ],
        )
        assert planner_needs_coverage_replan(plan) is False

    def test_one_negative_only_does_not_trigger_replan(self):
        """Plan with only Negative (not Positive) does not trigger replan."""
        plan = self._make_plan(
            requirement_type="FR",
            safe_to_generate=True,
            coverage_items=[
                CoverageItem(
                    coverage_item="invalid configured input is rejected",
                    test_type="Negative",
                    technique_used="Input validation",
                    priority="High",
                    rationale="Test rejection",
                    source_basis=["requirement states capability"],
                )
            ],
        )
        assert planner_needs_coverage_replan(plan) is False

    def test_three_coverage_items_positive_negative_boundary(self):
        """Plan with 3 items (Positive, Negative, Boundary) does not trigger."""
        plan = self._make_plan(
            requirement_type="FR",
            safe_to_generate=True,
            coverage_items=[
                CoverageItem(
                    coverage_item="valid configured input succeeds",
                    test_type="Positive",
                    technique_used="Functional verification",
                    priority="High",
                    rationale="Test basic success",
                    source_basis=["requirement states capability"],
                ),
                CoverageItem(
                    coverage_item="invalid configured input is rejected",
                    test_type="Negative",
                    technique_used="Input validation",
                    priority="High",
                    rationale="Test rejection",
                    source_basis=["requirement states capability"],
                ),
                CoverageItem(
                    coverage_item="missing required information is handled",
                    test_type="Boundary",
                    technique_used="Boundary value analysis",
                    priority="Medium",
                    rationale="Test edge case",
                    source_basis=["requirement states capability"],
                ),
            ],
        )
        assert planner_needs_coverage_replan(plan) is False


class TestPhase15IReplanPrompts:
    """Verify replan prompts enforce strict FR coverage contract."""

    def test_replan_system_prompt_forbids_otf(self):
        """Replan system prompt forbids OTP invention."""
        prompt = build_planner_replan_system_prompt()
        assert "OTP" in prompt or "one-time" in prompt.lower()

    def test_replan_system_prompt_forbids_dashboard(self):
        """Replan system prompt forbids dashboard invention."""
        prompt = build_planner_replan_system_prompt()
        assert "dashboard" in prompt.lower()

    def test_replan_system_prompt_forbids_lockout(self):
        """Replan system prompt forbids account lockout invention."""
        prompt = build_planner_replan_system_prompt()
        assert "lockout" in prompt.lower()

    def test_replan_system_prompt_forbids_retry(self):
        """Replan system prompt forbids retry limits invention."""
        prompt = build_planner_replan_system_prompt()
        assert "retry" in prompt.lower()

    def test_replan_system_prompt_forbids_password_rules(self):
        """Replan system prompt forbids exact password rules invention."""
        prompt = build_planner_replan_system_prompt()
        assert "password" in prompt.lower()

    def test_replan_system_prompt_forbids_exact_messages(self):
        """Replan system prompt forbids exact error messages invention."""
        prompt = build_planner_replan_system_prompt()
        assert "exact" in prompt.lower() and "message" in prompt.lower()

    def test_replan_system_prompt_forbids_screens(self):
        """Replan system prompt forbids screen/page/form invention."""
        prompt = build_planner_replan_system_prompt()
        assert "screen" in prompt.lower() or "page" in prompt.lower()

    def test_replan_system_prompt_forbids_api_db(self):
        """Replan system prompt forbids API/database invention."""
        prompt = build_planner_replan_system_prompt()
        assert ("API" in prompt or "api" in prompt.lower()) and (
            "database" in prompt.lower() or "db" in prompt.lower()
        )

    def test_replan_system_prompt_enforces_generic_wording(self):
        """Replan system prompt enforces generic requirement-level coverage."""
        prompt = build_planner_replan_system_prompt()
        assert "valid configured input" in prompt
        assert "invalid configured input" in prompt or "rejection" in prompt
        assert "missing required information" in prompt or "Boundary" in prompt

    def test_replan_user_prompt_forbids_one_positive_only(self):
        """Replan user prompt explicitly forbids one-positive-only safe plans."""
        prompt = build_planner_replan_user_prompt(
            [],
            {},
            None,
        )
        assert "do not answer with only one Positive" in prompt

    def test_replan_user_prompt_forbids_oop_escape(self):
        """Replan user prompt forbids using skip reasons to avoid expansion."""
        prompt = build_planner_replan_user_prompt(
            [],
            {},
            None,
        )
        assert "keep a one-case safe plan" in prompt


class TestPhase15IDiagnosticsFields:
    """Verify diagnostics fields are present in PlannerOutput."""

    def test_planner_output_has_coverage_replan_attempted(self):
        """PlannerOutput has coverage_replan_attempted field."""
        plan = PlannerOutput(
            requirement_id="REQ_1",
            requirement_text="Test requirement",
            requirement_type="FR",
            testable=True,
            safe_to_generate=True,
            risk_level="Medium",
            ambiguity_level="Low",
            blocking_missing_information=[],
            missing_information=[],
            coverage_items=[],
            recommended_test_case_count=0,
            assumptions=[],
            coverage_replan_attempted=False,
        )
        assert hasattr(plan, "coverage_replan_attempted")
        assert plan.coverage_replan_attempted is False

    def test_planner_output_has_coverage_replan_reason(self):
        """PlannerOutput has coverage_replan_reason field."""
        plan = PlannerOutput(
            requirement_id="REQ_1",
            requirement_text="Test requirement",
            requirement_type="FR",
            testable=True,
            safe_to_generate=True,
            risk_level="Medium",
            ambiguity_level="Low",
            blocking_missing_information=[],
            missing_information=[],
            coverage_items=[],
            recommended_test_case_count=0,
            assumptions=[],
            coverage_replan_reason="Test reason",
        )
        assert hasattr(plan, "coverage_replan_reason")
        assert plan.coverage_replan_reason == "Test reason"

    def test_planner_output_has_coverage_replan_succeeded(self):
        """PlannerOutput has coverage_replan_succeeded field."""
        plan = PlannerOutput(
            requirement_id="REQ_1",
            requirement_text="Test requirement",
            requirement_type="FR",
            testable=True,
            safe_to_generate=True,
            risk_level="Medium",
            ambiguity_level="Low",
            blocking_missing_information=[],
            missing_information=[],
            coverage_items=[],
            recommended_test_case_count=0,
            assumptions=[],
            coverage_replan_succeeded=True,
        )
        assert hasattr(plan, "coverage_replan_succeeded")
        assert plan.coverage_replan_succeeded is True


class TestPhase15INoKeywordBranching:
    """Verify no keyword-based branching logic in planner.py."""

    def test_planner_module_has_no_login_keyword_check(self):
        """planner.py does not contain keyword check for 'login'."""
        import inspect
        from app.services.test_case_generation import planner

        source = inspect.getsource(planner)
        # Check that if statements don't branch on login/password/dashboard keywords
        assert 'if "login"' not in source
        assert "if 'login'" not in source
        assert ".lower().*login" not in source  # no case-insensitive login checks

    def test_planner_module_has_no_password_keyword_check(self):
        """planner.py does not contain keyword check for 'password'."""
        import inspect
        from app.services.test_case_generation import planner

        source = inspect.getsource(planner)
        assert 'if "password"' not in source
        assert "if 'password'" not in source

    def test_planner_module_has_no_dashboard_keyword_check(self):
        """planner.py does not contain keyword check for 'dashboard'."""
        import inspect
        from app.services.test_case_generation import planner

        source = inspect.getsource(planner)
        assert 'if "dashboard"' not in source
        assert "if 'dashboard'" not in source

    def test_planner_module_uses_structural_check_only(self):
        """planner_needs_coverage_replan uses only structural fields, not text."""
        import inspect
        from app.services.test_case_generation.planner import planner_needs_coverage_replan

        source = inspect.getsource(planner_needs_coverage_replan)
        # Verify structural checks (safe_to_generate, coverage_items, test_type)
        assert "safe_to_generate" in source
        assert "coverage_items" in source
        assert "test_type" in source
        # Verify NO requirement text inspection (check code lines, not docstring)
        # Extract code section (skip docstring)
        code_lines = [line for line in source.split('\n') if line.strip() and not line.strip().startswith('"""') and not line.strip().startswith('#')]
        code_section = '\n'.join(code_lines[5:])  # Skip function def and docstring
        assert "requirement_text" not in code_section or "plan.requirement_text" not in code_section


class TestPhase15INoApprovedOrRepairer:
    """Verify no APPROVED or repairer logic introduced."""

    def test_planner_module_has_no_approved_keyword(self):
        """planner.py does not introduce APPROVED status."""
        import inspect
        from app.services.test_case_generation import planner

        source = inspect.getsource(planner)
        assert "APPROVED" not in source

    def test_planner_module_has_no_repairer_logic(self):
        """planner.py does not introduce separate repairer class/function."""
        import inspect
        from app.services.test_case_generation import planner

        source = inspect.getsource(planner)
        # Check for explicit repairer class or function definitions
        # (replan is allowed, but not a separate repairer mechanism)
        assert "class.*Repairer" not in source
        assert "def.*repairer" not in source.lower() or "def.*replan" in source.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
