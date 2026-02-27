#!/usr/bin/env bash
# =============================================================================
# simple-legal-doc Backend Validation Suite
# 8 integration tests against the Document Engine and Auditor.
#
# Run this suite after `docker compose up` and before configuring the
# MCP connector. All 8 tests must pass before proceeding to Step 3.
#
# Usage:
#   chmod +x connector/setup/validate_backend.sh
#   ./connector/setup/validate_backend.sh
# =============================================================================
set -uo pipefail

BACKEND="http://localhost:8000"
AUDITOR="http://localhost:8001"
PASS=0
FAIL=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
pass() { echo "  [PASS] $1"; ((PASS++)); }
fail() { echo "  [FAIL] $1"; ((FAIL++)); }

check_status() {
    local description="$1"
    local expected="$2"
    local actual="$3"
    if [ "$actual" = "$expected" ]; then
        pass "$description (HTTP $actual)"
    else
        fail "$description — expected HTTP $expected, got HTTP $actual"
    fi
}

check_body() {
    local description="$1"
    local pattern="$2"
    local body="$3"
    if echo "$body" | grep -q "$pattern"; then
        pass "$description"
    else
        fail "$description — pattern '$pattern' not found in response"
    fi
}

echo "=========================================="
echo "simple-legal-doc Backend Validation Suite"
echo "=========================================="
echo

# ---------------------------------------------------------------------------
# Test 1: Document Engine reachability
# ---------------------------------------------------------------------------
echo "[1/8] Document Engine — GET /templates"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND/templates")
check_status "GET /templates returns 200" "200" "$STATUS"

# ---------------------------------------------------------------------------
# Test 2: Template registry content
# ---------------------------------------------------------------------------
echo "[2/8] Template Registry — etk-decision registered"
BODY=$(curl -s "$BACKEND/templates")
check_body "etk-decision appears in template list" "etk-decision" "$BODY"

# ---------------------------------------------------------------------------
# Test 3: compliance-test-doc registered
# ---------------------------------------------------------------------------
echo "[3/8] Template Registry — compliance-test-doc registered"
check_body "compliance-test-doc appears in template list" "compliance-test-doc" "$BODY"

# ---------------------------------------------------------------------------
# Test 4: Schema endpoint — known template
# ---------------------------------------------------------------------------
echo "[4/8] Schema Endpoint — GET /templates/schema/etk-decision"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND/templates/schema/etk-decision")
check_status "GET /templates/schema/etk-decision returns 200" "200" "$STATUS"

# ---------------------------------------------------------------------------
# Test 5: Schema endpoint — unknown template returns 404
# ---------------------------------------------------------------------------
echo "[5/8] Schema Endpoint — 404 on unknown slug"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND/templates/schema/does-not-exist")
check_status "GET /templates/schema/does-not-exist returns 404" "404" "$STATUS"

# --------------------------------------------------------------------------- 
# Test 6: Generate endpoint — draft mode, valid payload 
# --------------------------------------------------------------------------- 
echo "[6/8] Generate Endpoint — POST /generate/compliance-test-doc?mode=draft" 
 
PAYLOAD1='{"subject": "Test: Unencrypted Public Database", "author": "Validation Suite", "doc_date": "26 February 2026", "risk_level": "HIGH", "justification": "This test document intentionally declares a HIGH risk level to verify that the rendering pipeline handles the risk_level field correctly across all three enum values.", "mitigation_strategy": "Immediate encryption of data at rest and in transit using AES-256, implementation of access controls, and mandatory security audit within 30 days."}'

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BACKEND/generate/compliance-test-doc?mode=draft" -H "Content-Type: application/json" -d "$PAYLOAD1") 
 
check_status "Draft generation returns 200" "200" "$HTTP_STATUS" 
 
PAYLOAD2='{"subject": "Header check", "author": "Validation Suite", "doc_date": "26 February 2026", "risk_level": "LOW", "justification": "Minimal test payload to verify response headers are correctly emitted by the backend on both draft and final mode responses.", "mitigation_strategy": "Minimal mitigation statement included to satisfy the 50-character minimum field constraint enforced by the Pydantic schema."}'

HEADERS=$(curl -s -D - -o /dev/null -X POST "$BACKEND/generate/compliance-test-doc?mode=draft" -H "Content-Type: application/json" -d "$PAYLOAD2") 
 
if echo "$HEADERS" | grep -qi "^X-Content-Hash:"; then 
    pass "X-Content-Hash header present in draft response" 
else 
    fail "X-Content-Hash header missing from draft response" 
fi

# ---------------------------------------------------------------------------
# Test 7: Generate endpoint — invalid payload returns 422
# ---------------------------------------------------------------------------
echo "[7/8] Generate Endpoint — 422 on schema violation"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "$BACKEND/generate/compliance-test-doc?mode=draft" \
    -H "Content-Type: application/json" \
    -d '{"subject": "Missing required fields"}')
check_status "Invalid payload returns 422" "422" "$STATUS"

# ---------------------------------------------------------------------------
# Test 8: Auditor reachability
# ---------------------------------------------------------------------------
echo "[8/8] Auditor — GET /health"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$AUDITOR/health")
check_status "GET /health returns 200" "200" "$STATUS"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo
echo "=========================================="
TOTAL=$((PASS + FAIL))
echo "Results: $PASS passed, $FAIL failed out of $TOTAL tests."
echo "=========================================="

if [ "$FAIL" -gt 0 ]; then
    echo
    echo "One or more tests failed. Do not proceed to MCP connector"
    echo "configuration until all backend health checks pass."
    exit 1
else
    echo
    echo "All tests passed. Proceed to Step 3."
    exit 0
fi