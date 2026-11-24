Feature: Weekly data sync
  As the maintainer, I want new portal data to reach the site without my help
  when the text still matches it, and to be asked for a review when it does not.

  Scenario: New data that keeps every quoted number publishes without review
    Given the published findings data
    And the portal adds a month that changes no quoted number
    When the sync checks the rebuilt data
    Then the data has changed
    And every claim holds
    And the sync opens a pull request to publish

  Scenario: New data that breaks a quoted number asks for a text review
    Given the published findings data
    And the portal revises the latest food inflation to 1.0%
    When the sync checks the rebuilt data
    Then the data has changed
    And the claim "Food inflation Aug 2026 (%)" fails
    And the sync opens a data-review issue instead of publishing

  Scenario: Nothing changed on the portal
    Given the published findings data
    When the sync checks the rebuilt data
    Then the data has not changed
    And the sync opens a pull request to publish

  Scenario: The watch list follows the registry
    Given the registry of findings
    Then every dataset pattern a finding needs is in data/datasets.txt
    And data/datasets.txt has no pattern that no page needs
