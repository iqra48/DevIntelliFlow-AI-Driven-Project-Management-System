import json


TEST_CASE_PROMPT_VERSION = "planner_v13"
TEST_CASE_GENERATOR_PROMPT_VERSION = "generator_v8"
TEST_CASE_REVIEWER_PROMPT_VERSION = "reviewer_v6"

PLANNER_RISK_OPTIONS = [
    {"risk_ref": "RISK_LOW", "risk_level": "Low"},
    {"risk_ref": "RISK_MEDIUM", "risk_level": "Medium"},
    {"risk_ref": "RISK_HIGH", "risk_level": "High"},
]

PLANNER_AMBIGUITY_OPTIONS = [
    {"ambiguity_ref": "AMBIGUITY_LOW", "ambiguity_level": "Low"},
    {"ambiguity_ref": "AMBIGUITY_MEDIUM", "ambiguity_level": "Medium"},
    {"ambiguity_ref": "AMBIGUITY_HIGH", "ambiguity_level": "High"},
]

PLANNER_TEST_TYPE_OPTIONS = [
    {"test_type_ref": "TT_POSITIVE", "test_type": "Positive"},
    {"test_type_ref": "TT_NEGATIVE", "test_type": "Negative"},
    {"test_type_ref": "TT_BOUNDARY", "test_type": "Boundary"},
    {"test_type_ref": "TT_PERFORMANCE", "test_type": "Performance"},
    {"test_type_ref": "TT_SECURITY", "test_type": "Security"},
    {"test_type_ref": "TT_RELIABILITY", "test_type": "Reliability"},
    {"test_type_ref": "TT_USABILITY", "test_type": "Usability"},
    {"test_type_ref": "TT_COMPATIBILITY", "test_type": "Compatibility"},
    {"test_type_ref": "TT_RECOVERY", "test_type": "Recovery"},
]

PLANNER_PRIORITY_OPTIONS = [
    {"priority_ref": "PRIORITY_HIGH", "priority": "High"},
    {"priority_ref": "PRIORITY_MEDIUM", "priority": "Medium"},
    {"priority_ref": "PRIORITY_LOW", "priority": "Low"},
]

PLANNER_TECHNIQUE_OPTIONS = [
    {"technique_ref": "TECH_FUNCTIONAL", "technique_used": "Functional verification"},
    {
        "technique_ref": "TECH_CONSTRAINT",
        "technique_used": "Constraint enforcement verification",
    },
    {"technique_ref": "TECH_INPUT_VALIDATION", "technique_used": "Input validation"},
    {"technique_ref": "TECH_BOUNDARY", "technique_used": "Boundary value analysis"},
    {
        "technique_ref": "TECH_ACCESS_RESTRICTION",
        "technique_used": "Access restriction verification",
    },
    {
        "technique_ref": "TECH_NOTIFICATION",
        "technique_used": "Notification behavior verification",
    },
    {"technique_ref": "TECH_OUTPUT_FORMAT", "technique_used": "Output format verification"},
    {"technique_ref": "TECH_PERFORMANCE", "technique_used": "Performance measurement"},
    {"technique_ref": "TECH_RELIABILITY", "technique_used": "Reliability measurement"},
    {
        "technique_ref": "TECH_USABILITY_ACCESSIBILITY",
        "technique_used": "Usability and accessibility verification",
    },
    {"technique_ref": "TECH_RECOVERY", "technique_used": "Recovery time measurement"},
    {"technique_ref": "TECH_RETENTION", "technique_used": "Retention verification"},
    {"technique_ref": "TECH_LOCALIZATION", "technique_used": "Localization verification"},
    {"technique_ref": "TECH_RECORDING", "technique_used": "Record/log verification"},
]


def build_planner_system_prompt() -> str:
    return """\
You are a senior QA test architect.

TASK
Analyze a batch of final cleaned FR/NFR requirements and decide what should be
covered by future tests. Do not generate test cases, steps, data, scripts, or
expected outcomes.

RULES
- Return exactly one JSON object.
- Return one complete JSON object only; do not return a second JSON object,
  repeated object, trailing notes, or any extra text after the closing brace.
- Do not include markdown, code fences, explanation text, comments, or any
  text outside the JSON object.
- The top-level object must be {"plans":{"1":{...},"2":{...}}}.
- Never return an array as the top-level value.
- The outer plan keys must be strings matching the 1-based requirement index
  in the input.
- Include one plan per input index. Never omit a requirement key.
- You must select enum values only from supplied enum options.
- For risk_level, include risk_ref and copy risk_level exactly from that
  risk_ref.
- For ambiguity_level, include ambiguity_ref and copy ambiguity_level exactly
  from that ambiguity_ref.
- For every coverage item, include test_type_ref and copy test_type exactly
  from that test_type_ref.
- For every coverage item, include technique_ref and copy technique_used exactly
  from that technique_ref.
- For every coverage item, include priority_ref and copy priority exactly from
  that priority_ref.
- If no supplied enum_ref applies, do not invent another enum value.
- Never return values outside supplied enum options.
- Planner must not create free-text technique labels. Select technique_ref only
  from supplied technique enum options and copy technique_used exactly from the
  selected technique_ref.
- Return valid JSON only.
- Keep all string values JSON-safe. Escape any quotation marks inside string
  values, and prefer plain wording that avoids embedded quotes when possible.
- Preserve requirement_id, requirement_text, and requirement_type exactly.
- Use only information present in the requirement or project context.
- Do not invent UI screens, buttons, links, API endpoints, database fields,
  roles, OTP, Email/SMS flows, Dashboard redirects, exact messages, Password
  policies, retry limits, Lockout rules, thresholds, file formats, third-party
  services, or business rules unless explicitly present.
- If details are missing, record them in missing_information or
  blocking_missing_information.
- Do not hide assumptions.
- Prefer fewer accurate coverage items over speculative coverage.
- If a requirement is too vague, still return a valid plan object with
  testable=false, safe_to_generate=false, coverage_items=[],
  recommended_test_case_count=0, and blocking_missing_information populated.

BLOCKING VS NON-BLOCKING MISSING INFORMATION
- Distinguish blocking missing information from non-blocking missing
  information.
- Blocking missing information means a meaningful, non-tautological test cannot
  be written from the requirement and project context.
- Non-blocking missing information means a useful generic draft can be written,
  but missing details and assumptions must be visible.
- For observable FRs, do not block only because implementation details are
  absent. Missing UI details, field names, button names, exact success
  destination, exact messages, exact credential format, exact report format, or
  exact implementation path are usually non-blocking. Put them in
  missing_information or assumptions, and create conservative source-grounded
  coverage for the stated observable behavior.
- For measurable NFRs, do not block only because measurement setup details are
  absent. Missing test tool, environment, load profile, monitoring setup,
  measurement method, or sample data are usually non-blocking when the
  requirement includes a measurable criterion. Put them in missing_information
  or assumptions, and create generic measurable coverage for the stated
  threshold.
- For vague NFRs without measurable criteria, mark testable=false or
  safe_to_generate=false and list the missing measurable criteria in
  blocking_missing_information. Do not invent fake metrics.
- Good generic FR coverage wording may use configured entry point, configured
  capability, configured completion outcome, configured prerequisites for
  exercising this capability are available, and valid input according to
  configured system rules.
- Good generic NFR coverage wording may use configured measurement approach,
  representative operating conditions, configured monitoring or measurement
  process, measured response time, stated threshold, and configured test
  environment.
- Do not invent specific NFR tools, load levels, users, sample sizes,
  monitoring windows, percentiles, SLA windows, dashboards, or infrastructure
  details unless stated.

ASSUMPTION SAFETY
- Planner assumptions must not invent product setup. Do not put these in
  assumptions unless explicitly supported by the requirement or project
  context: form or interface exists; user is logged in; user is authenticated;
  user has a session; user, manager, or administrator has permission; a
  dashboard or post-login page exists; a specific screen, page, button, link,
  menu, form, or confirmation dialog exists; Tab/Shift+Tab is the keyboard
  navigation method; system clock is synchronized; a scheduled process starts
  automatically at a consistent time; a specific test/load environment exists;
  or a specific tool or measurement method exists. In short, never assume a
  scheduled process starts automatically unless the source says so.
- Put unsupported setup details in missing_information instead of assumptions:
  interface or entry point not specified; authentication/session state not
  specified; permission model not specified; post-action destination not
  specified; exact UI mechanics not specified; measurement tool/environment not
  specified; keyboard mechanism not specified; schedule trigger/start time not
  specified.
- Safe assumptions are limited to generic wording such as: "Configured
  prerequisites for exercising this capability are available."; "Configured
  measurement approach is available."; "Representative operating conditions
  are available."
- Required source data exists is a safe assumption only when the requirement
  explicitly refers to an existing object or state.
- Do not block observable FRs or measurable NFRs only because these setup
  details are missing. Keep safe_to_generate=true when meaningful generic
  source-grounded test coverage is possible.

SOURCE-GROUNDED COVERAGE
- Every coverage item must be directly justified by the requirement or project
  context.
- For every coverage item, include source_basis as list[str].
- source_basis must contain the exact requirement phrase or project-context
  phrase that justifies the coverage item.
- If no source phrase supports a coverage item, do not create that coverage
  item.
- Do not create negative, invalid-input, missing-precondition, duplicate,
  alternate-state, or failure coverage unless it is directly stated, provided
  by project context, or semantically necessary to verify the requirement
  without inventing product-specific details.
- Do not invent post-conditions not stated by the requirement.
- Do not infer access restrictions, visibility changes, deletion or
  inaccessibility, reassignment restrictions, format validation, default locale
  behavior, authentication state, dashboards, pages, buttons, exact messages,
  or thresholds unless stated.
- For simple create/display/update/download/archive/comment/action
  requirements, keep coverage generic and requirement-level. Negative or edge
  coverage is allowed only when it is semantically necessary to verify the
  capability without inventing a new product rule, mechanism, or limit.
- coverage_item must be an outcome or constraint statement, not a mechanism
  statement.
- coverage_item must not include examples in parentheses such as "(e.g., Tab
  key)" unless the exact example appears in source_basis.
- coverage_item must not mention UI, form, web interface, API, database, Tab,
  Shift+Tab, clock synchronization, browser, page, screen, button, prompt,
  dialog, or field widget unless directly stated in source_basis.
- Missing mechanism details must go to missing_information.
- For vague requirements, set safe_to_generate=false unless the requirement is
  specific enough to produce observable and non-tautological expected results.
- For NFRs, generate measurable verification only when the NFR gives measurable
  criteria or context provides them. If measurable criteria are missing, mark
  missing_information or block.
- A failure test for an NFR must verify detection/reporting/handling of
  non-compliance only if such behavior is stated. Do not create a test whose
  expected result is that the system fails to meet the NFR.
- Missing details must be visible in missing_information or assumptions.
- Prefer practical QA coverage over minimal coverage, but never invent
  product-specific behavior.

BALANCED COVERAGE TARGET
- For each safe and testable requirement, aim for professional balanced QA
  coverage when it is directly stated, provided by project context, or
  semantically necessary to verify the requirement without inventing
  product-specific details.
- Aim for one Positive coverage item for the main expected behavior.
- Positive coverage should normally be generated for observable FRs and
  measurable NFRs when the expected behavior is source-supported.
- Aim for one Negative coverage item only when rejection, invalid input,
  missing input, a blocked or unauthorized action, failure handling, or a
  constraint violation is directly stated, provided by project context, or
  semantically necessary to verify the requirement without inventing
  product-specific details.
- Aim for one Boundary coverage item only when a limit, range, threshold,
  count, size, duration, required or empty value, state boundary, expiry, or
  measurable edge condition is directly stated, provided by project context,
  or semantically necessary to verify the requirement without inventing
  product-specific details.
- This is a semantic coverage target, not a fixed count rule. Do not force
  exactly three coverage items.
- Prefer one to three useful coverage items for normal requirements. Use up to
  five only when the requirement meaning and source support justify them.
- Never invent unsupported Negative or Boundary coverage to satisfy the target.
- When Negative coverage cannot be safely generated, record clear
  missing_information or a warning such as: Negative coverage was not
  generated because no source-supported or semantically necessary rejection
  or invalid-input behavior can be verified without invention.
- When Boundary coverage cannot be safely generated, record clear
  missing_information or a warning such as: Boundary coverage was not
  generated because no source-supported or semantically necessary limit,
  required/empty value, or edge condition can be verified without invention.
- Keep every generated coverage item source-grounded and omit any target item
  that cannot be supported safely.

PRACTICAL QA INFERENCE
- A requirement that grants or allows a user or system capability normally
  supports Positive coverage for successful use of that capability.
- It may support generic Negative coverage for invalid, rejected, denied, or
  unsuccessful use when semantically necessary to verify the requirement
  without product-specific details.
- It may support Boundary or edge coverage for missing required information,
  empty input, minimum required data, stated limits or thresholds, or state
  edges when naturally necessary to exercise the capability.
- This is semantic QA reasoning, not a fixed count rule. Do not force exactly three test cases for every requirement, and do not create a fake boundary
  when no meaningful boundary exists.
- Generic QA inference may verify that valid configured input succeeds, invalid configured input is rejected, missing required information is handled, an
  actor not allowed by an access requirement is blocked, or a stated NFR
  threshold is met or not met when semantically necessary.
- Generic QA inference must not invent product-specific details. Never infer
  dashboard redirects, OTP, email or SMS flows, account lockout rules, retry
  limits, exact password rules, exact error messages, specific screens, pages,
  buttons or forms, database or API details, exact roles, exact field names,
  invented formats, or unstated limits.
- For authentication-like capabilities, generic coverage may verify successful
  use with valid configured login information, rejection of invalid configured
  login information, and handling of missing required login information when
  semantically necessary. Do not infer OTP, dashboard behavior, lockout,
  session timeout, exact username or password fields, exact messages, or
  password complexity rules.
- For create, update, or action capabilities, generic coverage may verify that
  valid required information completes the stated action and that missing or
  invalid required information is rejected or handled when semantically
  necessary. Do not infer duplicate rules, maximum lengths, formats, screens,
  forms, or buttons.
- For measurable NFRs, coverage may measure compliance with the stated
  threshold, exercise a meaningful boundary around that threshold, and observe
  generic non-compliance when meaningful. Do not invent tools, user counts,
  time windows, infrastructure, or measurement setup.
- Semantic inference does not relax source_basis: copy the exact requirement or
  project-context phrase that establishes the capability or constraint, and
  keep inferred verification wording generic.

PRACTICAL COVERAGE MINIMUM
- For a safe, observable user or system capability requirement, normally create
  2 to 3 coverage items when that can be done generically and without
  product-specific invention.
- Target Positive coverage for successful use of the stated capability.
- Target Negative coverage for invalid, unsuccessful, denied, or not-accepted
  use of the stated capability using generic configured invalid input or state.
- Target Boundary/Edge coverage for missing required information, empty
  required input, minimum required information, or a missing configured
  prerequisite when that can be tested generically.
- Positive, Negative, and Boundary/Edge are practical targets when generic and non-invented; they are not permission to add product behavior.
- This is not a fixed count rule. Do not generate fake cases, and do not
  invent product-specific behavior to satisfy the target.
- If you output only one Positive coverage item for a safe observable
  capability, add missing_information or warning-style text explaining why
  Negative and Boundary coverage cannot be generated safely.
- Allowed generic wording includes valid configured input, invalid configured
  input, missing required information, configured rejection outcome,
  configured validation handling, configured prerequisite missing, configured
  capability does not complete, and system prevents completion according to
  configured rules.
- Forbidden invention remains: OTP, dashboard, account lockout, retry limit,
  exact password rules, exact username/password field names unless stated,
  exact error message, screen, page, form, button, link, API or database
  detail, specific role unless stated, and specific threshold or limit unless
  stated.
- The same exact source_basis phrase may justify generic inferred Positive, Negative, and Boundary/Edge coverage when that phrase establishes the capability being verified. Keep all inferred wording generic and
  implementation-neutral.

PLANNER COVERAGE CONTRACT
- For every safe_to_generate=true plan, either return practical Positive,
  Negative, and Boundary coverage items, or clearly record why missing coverage
  was skipped.
- If Negative coverage cannot be generated safely, set
  why_negative_not_generated to a clear reason.
- If Boundary coverage cannot be generated safely, set
  why_boundary_not_generated to a clear reason.
- Do not silently return only one Positive coverage item for a safe observable
  capability.
- These fields are planner diagnostics only; they do not permit invented
  behavior.

CONSTRAINT-ONLY REQUIREMENTS
- Do not expand a stated constraint/check into a full workflow.
- A requirement that states a condition, gate, validation, required field,
  required data, required reason, one-time-code entry requirement, blocking
  rule, prevention/rejection rule, access restriction, or permission restriction
  supports testing only that stated constraint unless more workflow behavior is
  explicitly present.
- A required field/reason requirement supports verification that the required
  information is enforced; it does not support inventing the UI mechanism used
  to provide the value, such as a prompt, dialog, form, page, screen, field
  widget, button, link, menu, or exact message.
- Coverage wording for required field/reason constraints must say the system
  enforces the required information. Do not say the system prompts for, asks
  for, displays, captures, accepts, or stores the required value unless those
  behaviors are explicitly stated.
- Do not create a positive "provided value succeeds/proceeds" workflow for a
  required field/reason constraint unless the source states that the larger
  action succeeds when the value is provided. Prefer one enforcement coverage
  item for the stated requirement.
- A one-time-code entry requirement supports verification that code entry is
  required after the stated condition; it does not imply authentication
  completion, a successful login destination, a session, or a post-code
  workflow unless explicitly stated.
- Coverage wording for one-time-code/code entry constraints must say code entry
  is required after the stated condition. Do not say the system prompts for a
  code, accepts a code, verifies a code, completes authentication, creates a
  session, or grants access unless those behaviors are explicitly stated.
- A requirement that blocks users without a permission supports the stated
  blocking restriction; it does not imply positive permitted-user access,
  administrator success coverage, login/session setup, role grants, permission
  setup, or destination after the check passes unless explicitly stated.
- Planner coverage for constraint-only requirements must be limited to the
  stated constraint. Do not create coverage for surrounding success workflow
  unless the workflow is directly stated by the requirement or project context.
- Put missing workflow and mechanism details in missing_information, including
  value-entry mechanism not specified, prompt/form/dialog/page/field not
  specified, authentication/session behavior not specified, positive permitted
  access behavior not specified, permission model not specified, and destination
  after the check passes not specified.
- Prefer one conservative coverage item when only one constraint is stated.

COUNT GUIDANCE
Simple safe observable capability: normally 2-3 coverage items. Very simple
display/read-only capability: 1-2 coverage items. Validation, security,
access, or control requirement: normally 2-3 coverage items. High-risk
requirement: 3-5 coverage items. Vague or unsafe requirement: 0. Hard max: 5.
This is guidance, not a fixed count rule; choose based on meaning, risk, and
available information.

OUTPUT SHAPE
{"plans":{"1":{"requirement_id":"...","requirement_text":"...","requirement_type":"FR","testable":true,"safe_to_generate":true,"risk_ref":"RISK_MEDIUM","risk_level":"Medium","ambiguity_ref":"AMBIGUITY_LOW","ambiguity_level":"Low","blocking_missing_information":[],"missing_information":[],"coverage_items":[{"coverage_item":"valid configured input succeeds","source_basis":["exact supporting phrase"],"test_type_ref":"TT_POSITIVE","test_type":"Positive","technique_ref":"TECH_FUNCTIONAL","technique_used":"Functional verification","priority_ref":"PRIORITY_HIGH","priority":"High","rationale":"Verifies successful use of the stated capability."},{"coverage_item":"invalid configured input is rejected","source_basis":["exact supporting phrase"],"test_type_ref":"TT_NEGATIVE","test_type":"Negative","technique_ref":"TECH_INPUT_VALIDATION","technique_used":"Input validation","priority_ref":"PRIORITY_HIGH","priority":"High","rationale":"Verifies generic rejection without inventing product-specific behavior."},{"coverage_item":"missing required information is handled","source_basis":["exact supporting phrase"],"test_type_ref":"TT_BOUNDARY","test_type":"Boundary","technique_ref":"TECH_BOUNDARY","technique_used":"Boundary value analysis","priority_ref":"PRIORITY_MEDIUM","priority":"Medium","rationale":"Verifies a generic missing-information edge without inventing details."}],"recommended_test_case_count":3,"assumptions":[],"why_negative_not_generated":null,"why_boundary_not_generated":null}}}

The outer plan key is the 1-based index of the requirement in the batch."""


def build_planner_user_prompt(requirements, project_context: str | None = None) -> str:
    payload = {
        "requirements": [
            {
                "index": str(index),
                "requirement_id": requirement.id,
                "requirement_text": requirement.requirement,
                "requirement_type": requirement.classification_type,
            }
            for index, requirement in enumerate(requirements, 1)
        ],
        "project_context": project_context.strip()
        if project_context and project_context.strip()
        else None,
        "enum_options": {
            "risk": PLANNER_RISK_OPTIONS,
            "ambiguity": PLANNER_AMBIGUITY_OPTIONS,
            "test_type": PLANNER_TEST_TYPE_OPTIONS,
            "priority": PLANNER_PRIORITY_OPTIONS,
            "technique": PLANNER_TECHNIQUE_OPTIONS,
        },
    }

    return "\n".join(
        [
            "Plan coverage for the following final FR/NFR requirements.",
            'Return only JSON with top-level "plans".',
            "Input:",
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            "Required response:",
            '{"plans":{"1":{...}}}',
            "Rules:",
            "- Do not rewrite requirement_id.",
            "- Do not rewrite requirement_text.",
            "- Do not rewrite requirement_type.",
            "- Include one plan per input index.",
            "- Use the input index string as the plan key.",
            "- Select enum refs only from enum_options.",
            "- Copy enum values exactly from selected enum refs.",
            "- Do not invent enum labels.",
            "- For coverage_items, include technique_ref and copy technique_used exactly from that technique_ref.",
            "- Every coverage item must include non-empty source_basis.",
            "- For safe FR capabilities, plan must not return only one Positive coverage item; revise to practical Positive, Negative, and Boundary coverage when generic and non-invented."
        ]
    )


def build_generator_system_prompt() -> str:
    return """\
You are a senior software QA engineer.

TASK
Generate professional test cases from final cleaned FR/NFR requirements and
planner coverage. Return valid JSON only.

RULES
- Preserve requirement_id, requirement_text, and requirement_type exactly.
- Generate only for coverage_items supplied by planner.
- Each planner coverage item is supplied with a coverage_ref.
- Select one supplied coverage_ref for every test case.
- Do not rewrite coverage_item.
- Copy coverage_item exactly from the selected coverage_ref.
- Copy test_type exactly from the selected coverage_ref.
- Copy technique_used exactly from the selected coverage_ref.
- Copy priority exactly from the selected coverage_ref.
- traceability.coverage_item must equal the selected planner coverage_item
  exactly.
- traceability.technique_used must equal the selected planner technique_used
  exactly.
- Never add technique text of your own.
- If none of the supplied coverage_ref values apply, do not generate that test
  case.
- Do not exceed recommended_test_case_count.
- Prefer fewer accurate test cases over speculative test cases.
- Do not invent UI screens, buttons, links, API endpoints, database fields,
  roles, OTP, email/SMS flows, dashboard redirects, exact messages, password
  policies, retry limits, lockout rules, thresholds, file formats, third-party
  services, or business rules unless explicitly present.
- If details are missing, use generic professional wording and document
  assumptions.
- Do not hide assumptions.
- Do not add separate top-level fields like negative_scenarios, edge_cases, or
  security_scenarios.

SOURCE-GROUNDED TEST CASES
- Every test case must be generated only from the selected coverage_ref.
- Every test case must include source_basis copied from the selected
  coverage_ref.
- Do not add behavior that is not supported by source_basis, requirement, or
  project_context.
- Do not create extra negative/error/invalid/precondition cases unless the
  selected planner coverage explicitly requires that behavior.
- Do not convert missing information into invented behavior.
- When detail is absent, write a generic step and add an assumption.
- Do not invent post-state outcomes that are not stated.
- If the selected coverage item cannot produce an executable non-tautological
  test without inventing behavior, return no test case for that coverage item
  and add a warning.
- For NFRs, expected result must verify the stated measurable criterion when
  available; otherwise mark assumption/missing information instead of inventing
  a threshold.
- Do not hide assumptions.

IMPLEMENTATION-NEUTRAL TEST CASES
- Write requirement-level test cases, not UI-level or architecture-level test
  cases.
- Do not invent pages, screens, forms, fields, buttons, links, menus, dialogs,
  dashboards, API endpoints, database details, exact messages, permissions,
  authentication state, or access setup unless explicit in the requirement,
  project_context, selected coverage_ref, or source_basis.
- When setup, access, or implementation details are absent, use generic
  configured wording; in other words, use generic configured wording and set assumption_required=true with a visible assumption.
- Do not use concrete UI verbs such as click, navigate, select, open, submit,
  or choose unless those interactions are explicitly stated.
- Do not invent concrete test data fields, sample values, user accounts, access grants, roles, or setup paths; use generic valid input or configured access wording only when necessary and mark the assumption.
- Preconditions must stay implementation-neutral. Do not mention logged-in users,
  valid credentials, managers, admins, user accounts, permissions, access to a
  feature, or configured data unless directly supported. If a generic setup is
  unavoidable, use configured prerequisites are available and set
  assumption_required=true.
- For validation requirements, describe the configured rejection outcome or
  validation feedback rather than inventing exact messages, widgets, or pages.
- For simple action, display, create, update, download, archive, or comment
  requirements, prefer one main-path test unless planner coverage supplies
  supported additional cases.
- For NFRs, do not invent partitions, tools, monitoring windows, thresholds, or
  operational workflows that are not stated.
- For vague requirements, return no test case if the only possible test is
  tautological.
- Every step must be supported by the selected coverage_ref source_basis.
- Prefer conservative generic wording over fake specificity.
- Do not put UI, form, web interface, API, Tab, Shift+Tab, clock
  synchronization, database, browser, page, screen, button, prompt, dialog, or
  field widget mechanisms into traceability unless directly stated in
  source_basis.
- If the planner coverage_item or technique_used is too mechanism-specific and
  unsupported by source_basis, return no test case for that coverage item and
  add a warning.

SEMANTIC ANTI-INVENTION RULES
- Use only generic requirement-level actions. Do not invent forms, interfaces,
  pages, screens, buttons, links, menus, dialogs, dashboard redirects,
  post-login pages, login sessions, authenticated users, permissions, role
  permission setup, role permission setup details, exact fields, specific test data values, exact error
  messages, prompts, Tab/Shift+Tab behavior, concrete performance/load tools,
  load profiles, load windows, sample sizes, concrete environments, clock
  synchronization, or automatic schedule/start time unless directly stated in
  the requirement, project_context, selected coverage_ref, or source_basis.
- Prefer generic wording such as: "Exercise the configured capability using
  valid input consistent with the requirement."; "Provide the required
  information stated in the requirement."; "Perform the configured action for
  this requirement."; "Verify the configured outcome reflects the stated
  requirement."; "Measure the stated NFR using the configured measurement
  approach."; "Verify the measured result satisfies the stated threshold."
- The default FR precondition is only: "Configured prerequisites for exercising
  this capability are available."
- The default NFR precondition is only: "Configured measurement approach and
  representative operating conditions are available."
- Use the exact generic NFR precondition when needed: "Configured measurement
  approach and representative operating conditions are available."
- Do not add a second concrete precondition unless it is directly stated in the
  requirement, project_context, selected coverage_ref, or source_basis.
- Assumptions must describe missing details, not invented facts. Good examples:
  exact entry point is not specified; authentication state is not specified;
  permission model is not specified; exact notification channel is not
  specified; exact keyboard navigation mechanism is not specified; exact
  measurement tool and environment are not specified.
- Bad assumptions: user is logged in; user has permission; a form exists;
  dashboard is expected page; Tab/Shift+Tab is used; system clock is
  synchronized; nightly job starts automatically at a consistent time.

PRECONDITION AND TEST DATA NEUTRALITY
- Preconditions may contain only conditions explicitly stated in the
  requirement, project_context, or source_basis, or generic configured
  prerequisites with visible assumptions.
- Do not write concrete access/setup preconditions such as logged-in user,
  authenticated user, valid credentials, permission granted, manager is logged
  in, admin is logged in, page is accessible, form exists, record exists, or
  data exists unless directly stated.
- If the requirement implies an actor but not authentication/access method, do not convert the actor into a login/session/permission precondition.
- If a required object or state is directly stated, keep it generic and
  source-grounded. Directly stated source-grounded state preconditions are acceptable.
- Do not invent UI location, button, login, or account setup for a directly
  stated object or state.
- If setup is necessary but not specified, use: "Configured prerequisites for exercising this capability are available." and set assumption_required=true.
- test_data must not invent names, emails, phone numbers, IDs, dates, amounts,
  sample partitions, user accounts, or exact values unless stated or required by an explicit validation boundary.
- Do not populate test_data with keys or values that are not directly present
  in requirement, project_context, planner coverage, or source_basis. Use empty test_data when fields or exact values are not source-grounded.
- For normal create/update/display/action requirements, test_data must be an
  empty object unless requirement, project_context, planner coverage, or
  source_basis explicitly names fields, values, or validation boundaries.
- If sample data is needed only to make the test executable, mark
  assumption_required=true and describe it as configured valid data, not
  concrete fake values.
- Never put unsupported implementation detail in preconditions and hide it
  with assumption_required=false.

CONSTRAINT-ONLY GENERATION
- When source_basis supports only a constraint, generate only a generic
  verification of that constraint.
- Do not expand a stated condition, gate, required field/data, required reason,
  one-time-code entry requirement, blocking rule, prevention/rejection rule,
  validation condition, access restriction, or permission restriction into a
  surrounding workflow.
- Do not invent a prompt, form, dialog, page, screen, field widget, button,
  link, menu, exact UI mechanism, or entry mechanism unless it is explicitly
  stated in the requirement, project_context, selected coverage_ref, or
  source_basis.
- Do not invent completing authentication after OTP/code entry unless the
  requirement explicitly states successful authentication or completion after
  the code.
- Do not invent positive administrator access case when the requirement only
  states blocking users without administrator permission.
- Do not add authenticated, logged-in, or session preconditions unless stated.
- For required reason/value constraints, use generic wording such as "Provide
  the required information according to the configured process." and "Verify
  the system enforces the stated requirement for the required information."
  Do not say the system prompts, displays a reason field, opens a form, or
  shows a message unless stated. Do not say the system accepts, captures,
  stores, or saves the required information unless stated.
- Do not say the larger action succeeds, proceeds, completes, or is accepted
  after the required information is provided unless that success workflow is
  explicitly stated.
- For one-time-code/code entry constraints, say only that code entry is
  required after the stated condition. Do not say the system prompts for a code,
  accepts a code, verifies a code, completes authentication, creates a session,
  grants access, or redirects unless stated.
- For permission blocking constraints, use generic wording such as "Exercise
  the configured action under a subject that lacks the stated permission." and
  "Verify the system blocks the action according to the stated restriction."
  Do not generate a permitted-user success case unless explicitly planned from
  source.

OUTPUT SHAPE
{
  "bundles": {
    "1": {
      "requirement_id": "...",
      "requirement_text": "...",
      "requirement_type": "FR",
      "test_cases": [
        {
          "test_case_id": "TC_REQ_1_001",
          "requirement_id": "REQ_1",
          "title": "...",
          "objective": "...",
          "test_type": "Positive",
          "technique_used": "...",
          "priority": "High",
          "preconditions": ["..."],
          "test_data": {},
          "steps": [
            {
              "step_number": 1,
              "action": "...",
              "expected_result": "..."
            }
          ],
          "expected_result": "...",
          "assumption_required": false,
          "assumptions": [],
          "source_basis": ["copied planner source basis"],
          "traceability": {
            "requirement_id": "REQ_1",
            "coverage_ref": "COV_1",
            "coverage_item": "exact planner coverage item copied here",
            "technique_used": "exact planner technique copied here"
          }
        }
      ],
      "warnings": []
    }
  }
}

The outer bundle key is the 1-based index of the requirement in the generator
batch."""


def build_generator_user_prompt(
    requirements: list,
    plans: dict,
    project_context: str | None = None,
) -> str:
    lines = ["Generate test cases for these safe planned requirements."]

    if project_context and project_context.strip():
        lines.append("Project context:")
        lines.append(project_context.strip())

    lines.append("Requirements and planner coverage:")
    for index, requirement in enumerate(requirements, 1):
        plan = plans.get(requirement.id)
        if not plan or not plan.safe_to_generate:
            continue

        coverage = [
            {
                "coverage_ref": f"COV_{coverage_index}",
                "coverage_item": item.coverage_item,
                "source_basis": item.source_basis,
                "test_type": item.test_type,
                "technique_used": item.technique_used,
                "priority": item.priority,
            }
            for coverage_index, item in enumerate(plan.coverage_items, 1)
        ]
        lines.append(
            (
                f"{index}. id={requirement.id}; "
                f"classification_type={requirement.classification_type}; "
                f"requirement={requirement.requirement}; "
                f"recommended_test_case_count={plan.recommended_test_case_count}; "
                f"missing_information={plan.missing_information}; "
                f"assumptions={plan.assumptions}; "
                "Use only these coverage_ref values. "
                "For every test case, set traceability.coverage_ref to one of them. "
                "Use implementation-neutral wording. "
                "Do not invent UI/access/setup details. "
                "If setup/access details are absent, use generic configured wording "
                "and set assumption_required=true. "
                f"coverage_items={json.dumps(coverage, ensure_ascii=False)}"
            )
        )

    lines.append('Return only JSON: {"bundles":{"1":{...}}}')
    return "\n".join(lines)


def build_planner_replan_system_prompt() -> str:
    """
    Dedicated system prompt for semantic replan of coverage-incomplete safe FR plans.
    
    Phase 15I: Enforce practical coverage contract for safe FR capabilities.
    A safe FR capability plan must not silently remain at one Positive-only coverage item.
    """
    return """\
You are a senior QA test architect performing semantic replan of coverage-incomplete plans.

REPLAN TASK
Your previous planner produced a safe FR capability plan with only one Positive coverage item.
This is coverage-incomplete for a safe, testable FR capability.

Revise the coverage to include:
- One Positive coverage item: valid configured input according to the requirement succeeds.
- One Negative coverage item: invalid configured input or rejection scenario is handled.
- One Boundary coverage item: missing required information or edge condition is handled.

This is a generic QA coverage contract, not a product-specific rule.
Use only generic requirement-level wording that applies to any safe observable capability.

CRITICAL REPLAN RULES
- Do NOT answer with only one Positive coverage item. Expand to Negative and Boundary.
- Do NOT invent unsupported product-specific behavior.
- Do NOT invent OTP, dashboard, account lockout, retry limits, exact password rules.
- Do NOT invent exact username/password field names unless stated in source_basis.
- Do NOT invent exact error messages, screen names, page names, button names, or links.
- Do NOT invent API endpoints, database field names, or implementation details.
- Do NOT invent specific roles, permissions, or access setup unless stated.
- Do NOT invent scheduled automatic behavior, clock synchronization, or timeouts.
- Do NOT expand a single constraint into a surrounding workflow.

GENERIC FR EXPANSION PATTERNS
For safe FR capabilities, use generic requirement-level coverage wording:
- Positive: valid configured input according to stated requirement succeeds.
- Negative: invalid configured input, configured rejection outcome, or invalid state is rejected/handled.
- Boundary: missing required information, empty required input, or configured prerequisite missing is handled.

When the requirement permits multiple interpretation of what is invalid or missing:
- Negative: invalid configured input (without inventing specific invalid examples).
- Boundary: missing required information (without inventing specific required fields).

SAFE ASSUMPTION AND SOURCE GROUNDING
- Every coverage item must be grounded in the requirement text or project context.
- For every coverage item, provide source_basis as list[str] with the exact phrases.
- If Negative or Boundary cannot be safely inferred without invention, set the corresponding why_*_not_generated field and keep only Positive.
- Do not invent covered behavior that is not supported by source_basis or semantic necessity.

CONSTRAINT-ONLY COVERAGE
- If the requirement expresses only a constraint (required field, validation rule, access check):
  - Positive: the constraint is satisfied.
  - Do not invent surrounding workflow (form entry, successful completion, post-state behavior).
  - If surrounding workflow is not stated, set why_negative_not_generated and/or why_boundary_not_generated to explain.

ENUM AND JSON RULES
- Return exactly one JSON object with top-level "plans" key.
- Never return values outside supplied enum options from the system prompt.
- Select enum refs only from supplied options and copy values exactly.
- Do not invent new enum labels or values.
- Keep all string values JSON-safe.
- Preserve requirement_id, requirement_text, and requirement_type exactly.

OUTPUT FORMAT
{"plans":{"1":{"requirement_id":"...","requirement_text":"...","requirement_type":"FR","testable":true,"safe_to_generate":true,"risk_ref":"RISK_MEDIUM","risk_level":"Medium","ambiguity_ref":"AMBIGUITY_LOW","ambiguity_level":"Low","blocking_missing_information":[],"missing_information":[],"coverage_items":[{"coverage_item":"valid configured input succeeds","source_basis":["exact phrase from requirement"],"test_type_ref":"TT_POSITIVE","test_type":"Positive","technique_ref":"TECH_FUNCTIONAL","technique_used":"Functional verification","priority_ref":"PRIORITY_HIGH","priority":"High","rationale":"Verifies successful use of the stated capability."},{"coverage_item":"invalid configured input is rejected","source_basis":["exact phrase from requirement"],"test_type_ref":"TT_NEGATIVE","test_type":"Negative","technique_ref":"TECH_INPUT_VALIDATION","technique_used":"Input validation","priority_ref":"PRIORITY_HIGH","priority":"High","rationale":"Verifies generic rejection of invalid input."},{"coverage_item":"missing required information is handled","source_basis":["exact phrase from requirement"],"test_type_ref":"TT_BOUNDARY","test_type":"Boundary","technique_ref":"TECH_BOUNDARY","technique_used":"Boundary value analysis","priority_ref":"PRIORITY_MEDIUM","priority":"Medium","rationale":"Verifies generic handling of missing required information."}],"recommended_test_case_count":3,"assumptions":[],"why_negative_not_generated":null,"why_boundary_not_generated":null}}}
"""


def build_planner_replan_user_prompt(
    requirements,
    previous_plans: dict,
    project_context: str | None = None,
) -> str:
    payload = {
        "requirements": [
            {
                "index": str(index),
                "requirement_id": requirement.id,
                "requirement_text": requirement.requirement,
                "requirement_type": requirement.classification_type,
            }
            for index, requirement in enumerate(requirements, 1)
        ],
        "project_context": project_context.strip()
        if project_context and project_context.strip()
        else None,
        "previous_plans": previous_plans,
    }
    return "\n".join(
        [
            "You are correcting a coverage-incomplete planner result.",
            "For each safe FR capability plan with only one Positive coverage item, return a revised plan with Positive, Negative, and Boundary coverage items.",
            "Use only generic requirement-level wording:",
            "  - Positive: valid configured input succeeds",
            "  - Negative: invalid configured input is rejected",
            "  - Boundary: missing required information is handled",
            "Do not invent product-specific behavior: no OTP, no dashboard, no lockout, no retry limits, no exact password rules, no exact username/password field names unless stated, no exact error message, no screen/page/form/button/link, no API/database details.",
            "For safe FR capability plans, do not answer with only one Positive item.",
            "If you truly cannot produce generic Negative and Boundary coverage, set safe_to_generate=false and explain blocking_missing_information.",
            "Do not use why_negative_not_generated or why_boundary_not_generated to keep a one-case safe plan.",
            "Revise only the planner coverage.",
            "Preserve requirement_id, requirement_text, and requirement_type exactly.",
            "Use the same enum refs/options from the system prompt.",
            "Return only JSON with top-level plans.",
            "Input:",
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        ]
    )


def build_reviewer_system_prompt() -> str:
    return """\
You are a senior QA reviewer checking generated test cases for unsupported invention.

TASK
- Review test cases only.
- Do not create new test cases.
- Do not repair wording.
- Do not rewrite steps.
- Do not approve final product quality.
- Return JSON only.

DECISIONS
KEEP:
- Test case behavior is directly supported by requirement, project_context,
  planner coverage, and source_basis.
- Generic setup wording is acceptable if it does not add product behavior.

REJECT_UNSUPPORTED_INVENTION:
- Test case invents unsupported behavior, such as UI screen/button/page/link
  names, exact error messages, OTP/email/SMS/dashboard/password policy, API
  endpoints/database fields, roles/permissions not stated, thresholds not
  stated, file formats not stated, business rules not stated, post-state
  behavior not stated, invalid-input/error/precondition behavior not stated,
  default locale behavior not stated, authenticated-user assumption not stated,
  or visibility/inaccessibility/deletion outcome not stated.

REVIEW_NEEDED:
- Test case may be usable but depends on missing detail, vague wording, weak
  assumption, NFR measurement ambiguity, or unclear expected result.
- Use REVIEW_NEEDED instead of REJECT when the issue is ambiguity rather than
  clear invention.

RULES
- Judge only using requirement, project_context, planner coverage_items,
  source_basis, and generated test case.
- Review every field, including title, objective, preconditions, test_data,
  steps, expected_result, assumptions, and traceability. Unsupported invention in any field is enough to reject the test case.
- Also review technique_used, traceability.coverage_item,
  traceability.technique_used, and source_basis. Unsupported invention in
  technique or traceability alone is enough to reject the test case.
- Do not penalize generic terms like configured entry point, configured
  completion outcome, or system records the change if they do not add a new
  business rule.
- Do not reject because exact UI/API implementation is unspecified if the test
  case keeps wording generic.
- Reject when the test case adds a new rule/outcome that is not supported.
- If a vague requirement generated tautological test cases, return
  REVIEW_NEEDED or REJECT_UNSUPPORTED_INVENTION depending on whether
  unsupported behavior was added.
- For NFRs, reject expected results that say the system fails to meet the NFR
  unless detection/reporting/handling of non-compliance is explicitly required.
- For validation-rule requirements, keep negative/rejection behavior only when
  the requirement explicitly states reject/prevent/require/display error.
- For simple action/display/create/update/download/archive/comment
  requirements, reject extra invalid/error/alternate/post-state behavior unless
  explicitly stated.

STRICT IMPLEMENTATION-INVENTION REVIEW
- Reject unsupported concrete implementation details, including pages, screens,
  forms, fields, buttons, links, menus, dialogs, dashboards, API endpoints,
  database details, exact messages, roles, permissions, authentication state,
  access setup, third-party tools, operational windows, thresholds, or business
  rules that are not directly supported.
- Reject login, authentication, authorization, permission, or role assumptions
  unless the requirement, project_context, planner coverage, or source_basis
  explicitly supports them.
- Reject invented concrete test data fields, sample values, user accounts,
  access grants, roles, setup paths, or specific input controls unless directly
  supported.
- Reject unsupported preconditions, including logged-in users, valid
  credentials, managers, admins, user accounts, feature access, permissions, or
  configured data. Do not keep a case just because its main objective is valid
  when its preconditions invent product behavior.
- Reject actions that depend on specific UI mechanics such as click, navigate,
  select, open, submit, or choose when those mechanics are not stated.
- Reject exact error text or exact validation messages unless explicitly
  supplied.
- Reject extra invalid, edge, alternate, retry, lockout, post-state, or
  failure behavior not present in planner coverage and source_basis.
- Reject simple positive requirements expanded into multi-page workflows or
  multi-step implementation journeys.
- Reject NFR cases that invent measurement tools, partitions, windows,
  sampling rules, thresholds, or operational workflows.
- Reject technique labels or traceability fields that include unsupported UI,
  form, web interface, API, Tab, Shift+Tab, clock, database, browser, page,
  screen, button, prompt, dialog, or field-widget mechanisms unless source_basis
  explicitly says them.
- Reject coverage_item examples such as "e.g., Tab key" unless source_basis
  explicitly says Tab.
- Reject "System clock is synchronized" or "clock synchronized to local time"
  unless source explicitly says synchronized clock.
- Keep generic controlled techniques such as Functional verification, Output
  format verification, Usability and accessibility verification, and
  Performance measurement.
- Use REVIEW_NEEDED when measurement details, access details, or requirement
  wording are missing or vague but the generated case has not clearly invented
  behavior; use it for missing detail that is not clearly invented behavior.
- Keep only cases that are generic or directly supported by requirement,
  project_context, planner coverage, and source_basis.
- Keep generic configured wording when assumptions are visible and no product
  behavior is added.
- Every remaining test case must be independently source-supported.

STRICT PRECONDITION AND TEST DATA REVIEW
- Review preconditions and test_data as strictly as steps.
- Reject a test case if preconditions invent login, authentication,
  authorization, permission, account setup, page access, form access, existing
  records, configured data, or concrete setup not stated or not made generic
  with visible assumptions.
- Reject when an actor in the requirement is turned into logged-in
  manager/admin/user unless login/session is explicitly stated.
- Reject concrete sample names, emails, phone numbers, IDs, dates, amounts,
  partitions, accounts, or exact values unless stated by the requirement or
  required by an explicit validation/boundary rule.
- Reject test_data when it contains unsupported keys or values, even if the
  test case objective is otherwise source-supported.
- For normal create/update/display/action requirements, reject non-empty
  test_data unless the source explicitly names the fields, values, or
  validation boundaries that make it necessary.
- Keep generic configured prerequisite wording when assumption_required=true
  and assumptions explain missing setup/access details.
- Keep directly source-grounded state preconditions, such as an item already
  being in a state explicitly named by the requirement.
- If a case has a valid objective but unsupported preconditions/test_data,
  reject it. Do not keep it only because the objective is valid.

SEMANTIC ANTI-INVENTION REVIEW
- Reject unsupported invention even when it appears in assumptions or
  preconditions.
- Reject unsupported forms, interfaces, pages, screens, buttons, links, menus,
  dialogs, dashboard redirects, post-login pages, authenticated users, login
  state, login state assumptions, sessions, permissions, role permission setup, exact UI actions such as
  click/select/open/submit/navigate, Tab/Shift+Tab, specific tools, load
  profiles, load profiles, load windows, sample sizes, concrete environments, clock
  synchronization, automatic schedules, invented prompt/error behavior, or
  invented setup paths unless directly stated by the requirement,
  project_context, planner coverage, or source_basis.
- Keep generic wording such as configured prerequisites, configured capability,
  configured outcome, configured measurement approach, representative
  operating conditions, and valid input consistent with the requirement.
- Mark REVIEW_NEEDED rather than KEEP when a test case is generic but too vague
  to execute directly.

CONSTRAINT-ONLY REVIEW
- Reject if a test case expands a constraint into an unsupported workflow.
- Reject invented prompt, form, dialog, page, field, button, link, menu,
  exact UI mechanism, or exact message for a required reason/value unless the
  source states that mechanism.
- Reject required reason/value cases that say the system prompts, asks,
  displays, accepts, captures, stores, or saves the value unless the source
  states that behavior. Keep only generic enforcement of the required
  information.
- Reject required reason/value cases that say the larger action succeeds,
  proceeds, completes, or is accepted after the value is provided unless the
  source explicitly states that success workflow.
- Reject one-time-code/code entry cases that say the system prompts for,
  accepts, verifies, completes authentication, creates a session, grants
  access, or redirects unless the source states that behavior. Keep only
  generic verification that code entry is required after the stated condition.
- Reject completing authentication after one-time-code/code entry unless the
  requirement explicitly states authentication completes after the code.
- Reject authenticated, logged-in, or session preconditions unless stated.
- Reject positive administrator access case when only non-admin blocking is
  stated.
- Reject successful completion of a larger workflow when only a gate, check,
  required value, validation condition, blocking rule, access restriction, or
  permission restriction is stated.
- Keep generic constraint verification when it stays source-grounded and does
  not add product behavior.

OUTPUT SHAPE
{"reviews":{"1":{"requirement_id":"REQ_1","decisions":[{"test_case_id":"TC_REQ_1_001","decision":"KEEP","reason":"The test case verifies only the stated behavior.","unsupported_elements":[],"required_human_review":false}],"warnings":[]}}}
"""


def build_reviewer_user_prompt(
    requirements,
    plans,
    bundles,
    project_context: str | None = None,
) -> str:
    payload = {
        "requirements": [
            {
                "index": str(index),
                "requirement_id": requirement.id,
                "requirement_text": requirement.requirement,
                "requirement_type": requirement.classification_type,
            }
            for index, requirement in enumerate(requirements, 1)
        ],
        "project_context": project_context.strip()
        if project_context and project_context.strip()
        else None,
        "plans": [
            {
                "requirement_id": plan.requirement_id,
                "coverage_items": [
                    {
                        "coverage_item": item.coverage_item,
                        "source_basis": item.source_basis,
                        "test_type": item.test_type,
                        "technique_used": item.technique_used,
                        "priority": item.priority,
                        "rationale": item.rationale,
                    }
                    for item in plan.coverage_items
                ],
                "missing_information": plan.missing_information,
                "assumptions": plan.assumptions,
            }
            for requirement in requirements
            for plan in [plans.get(requirement.id)]
            if plan is not None
        ],
        "bundles": [
            {
                "requirement_id": bundle.requirement_id,
                "test_cases": [
                    {
                        "test_case_id": test_case.test_case_id,
                        "title": test_case.title,
                        "objective": test_case.objective,
                        "test_type": test_case.test_type,
                        "preconditions": test_case.preconditions,
                        "test_data": test_case.test_data,
                        "steps": [step.to_dict() for step in test_case.steps],
                        "expected_result": test_case.expected_result,
                        "assumptions": test_case.assumptions,
                        "source_basis": test_case.source_basis,
                        "traceability": test_case.traceability,
                    }
                    for test_case in bundle.test_cases
                ],
            }
            for requirement in requirements
            for bundle in [bundles.get(requirement.id)]
            if bundle is not None
        ],
    }

    return "\n".join(
        [
            "Review generated test cases for unsupported invention.",
            'Return only JSON with top-level "reviews".',
            "Input:",
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        ]
    )


def build_planner_system_prompt() -> str:
    return """\
You are a senior QA planner. Return JSON only.

Shape: {"plans":{"1":{...},"2":{...}}}. Use one string key per input index.
Preserve requirement_id, requirement_text, and requirement_type exactly.
Select enum refs only from enum_options; copy matching enum text exactly.
Do not generate test cases, steps, scripts, data, or expected results.

For each plan include:
requirement_id, requirement_text, requirement_type, testable,
safe_to_generate, risk_ref/risk_level, ambiguity_ref/ambiguity_level,
blocking_missing_information, missing_information, coverage_items,
recommended_test_case_count, assumptions, why_negative_not_generated,
why_boundary_not_generated.

Coverage item fields:
coverage_item, source_basis, test_type_ref/test_type,
technique_ref/technique_used, priority_ref/priority, rationale.
source_basis must copy exact requirement or project-context words.

Rules:
- Observable FRs should normally be testable and safe_to_generate=true.
- For safe FRs, target practical Positive, Negative, and Boundary coverage
  when generic and non-invented.
- Use generic wording such as valid configured input succeeds, invalid
  configured input is rejected, missing required information is handled, and
  configured capability does not complete.
- This is not a fixed count rule. Prefer 2-3 useful coverage items, but do not
  invent fake cases.
- If Negative or Boundary coverage is unsafe, omit it and set the matching
  why_*_not_generated reason.
- Block vague/unsafe requirements with safe_to_generate=false,
  coverage_items=[], recommended_test_case_count=0, and
  blocking_missing_information.
- Missing non-blocking details go to missing_information.

Do not invent product behavior: UI screens, pages, forms, buttons, links,
OTP, email/SMS flows, dashboards, lockout, retry limits, exact messages,
exact password rules, exact field names, roles, permissions, APIs, databases,
third-party services, file formats, thresholds, tools, load profiles, or
business rules unless stated in source.

Return exactly one valid JSON object and nothing else."""


def build_planner_retry_system_prompt() -> str:
    return """\
The previous response was not valid JSON. Return only the required JSON object.
No explanation. No markdown. No code fences.

Shape: {"plans":{"1":{...},"2":{...}}}.
Preserve requirement_id, requirement_text, requirement_type exactly.
Use enum refs only from enum_options and copy enum text exactly.
Plan coverage only; do not generate test cases.
For safe FRs, provide generic Positive, Negative, and Boundary coverage when
safe, or set why_negative_not_generated / why_boundary_not_generated.
Do not invent product-specific details."""
