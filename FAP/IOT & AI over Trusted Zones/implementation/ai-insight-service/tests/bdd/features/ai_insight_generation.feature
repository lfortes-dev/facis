Feature: AI insight generation
  Validate AI insight endpoints using business-readable scenarios.

  Scenario: Energy anomaly detection
    Given a valid UTC insight window
    And anomaly report parameters are set
    When I request AI insight generation at "/api/v1/insights/anomaly-report"
    Then the response status code is 200
    And the returned insight type is "anomaly-report"
    And LLM metadata indicates successful generation
    And the insight response format is valid

  Scenario: Smart City event impact analysis
    Given a valid UTC insight window
    When I request AI insight generation at "/api/v1/insights/city-status"
    Then the response status code is 200
    And the returned insight type is "city-status"
    And the insight summary contains generated content
    And the insight response format is valid

  Scenario Outline: Insight format validation
    Given a valid UTC insight window
    And a request payload is prepared for "<endpoint>"
    When I request AI insight generation at "<endpoint>"
    Then the response status code is 200
    And the endpoint insight type is correct for "<endpoint>"
    And the insight response format is valid

    Examples:
      | endpoint                         |
      | /api/v1/insights/anomaly-report |
      | /api/v1/insights/city-status    |
      | /api/v1/insights/energy-summary |

  Scenario: Anomaly report include_data returns analytics context
    Given a valid UTC insight window
    And anomaly report parameters are set
    And include_data is enabled
    When I request AI insight generation at "/api/v1/insights/anomaly-report"
    Then the response status code is 200
    And the response contains analyzed window data

  Scenario: Latest and output lookup after generation
    Given a valid UTC insight window
    When I generate a city status insight
    And I request the latest insights snapshot
    Then the response status code is 200
    And latest city-status output id matches the created output id
    When I request the created output by id
    Then the output lookup succeeds with city-status content

  Scenario: Output lookup for missing id returns not found
    When I request output by id "does-not-exist"
    Then the response status code is 404

  Scenario: Invalid window returns bad request
    Given an invalid reversed UTC insight window
    When I request AI insight generation at "/api/v1/insights/anomaly-report"
    Then the response status code is 400
    And the error detail contains "earlier"

  Scenario: Invalid energy summary payload returns validation error
    Given an incomplete payload for energy summary
    When I request AI insight generation at "/api/v1/insights/energy-summary"
    Then the response status code is 422

  Scenario: Pipeline falls back when LLM is unavailable
    Given a valid UTC insight window
    And anomaly report parameters are set
    And LLM upstream is unavailable
    When I request AI insight generation at "/api/v1/insights/anomaly-report"
    Then the response status code is 200
    And fallback metadata indicates "integration llm down"

  Scenario: Pipeline falls back when LLM output is not JSON
    Given a valid UTC insight window
    And LLM output is plain text
    When I request AI insight generation at "/api/v1/insights/city-status"
    Then the response status code is 200
    And fallback summary is returned

  Scenario: Pipeline falls back when LLM output schema is invalid
    Given a valid UTC insight window
    When I request energy summary insight with invalid LLM schema output
    Then the response status code is 200
    And fallback metadata indicates "LLM output does not match expected schema"

  Scenario: Pipeline skips LLM when no data rows are analyzed
    Given a valid UTC insight window
    And anomaly report parameters are set
    And no anomaly rows are available
    When I request AI insight generation at "/api/v1/insights/anomaly-report"
    Then the response status code is 200
    And fallback metadata indicates "LLM skipped due to insufficient data (rows_analyzed=0)"

  Scenario: Policy enforcement requires access headers
    Given governance checks are enabled
    Given a valid UTC insight window
    And anomaly report parameters are set
    When I request AI insight generation at "/api/v1/insights/anomaly-report"
    Then the response status code is 403

  Scenario: Policy enforcement requires consumer role
    Given governance checks are enabled
    Given a valid UTC insight window
    And anomaly report parameters are set
    And policy headers contain a non-consumer role
    When I request AI insight generation at "/api/v1/insights/anomaly-report"
    Then the response status code is 403

  Scenario: Rate limiting returns too many requests
    Given governance checks are enabled
    Given a valid UTC insight window
    And anomaly report parameters are set
    And valid policy headers are provided
    When I send two anomaly insight requests under governance
    Then the first response status code is 200
    And the second response status code is 429
    And the second response has retry-after header

  Scenario: Successful city status hides llm_error in metadata
    Given a valid UTC insight window
    When I request AI insight generation at "/api/v1/insights/city-status"
    Then the response status code is 200
    And llm_error is null in metadata

  Scenario: Latest endpoint is empty before any insight generation
    When I request the latest insights snapshot
    Then the response status code is 200
    And latest insights are empty for all insight types
