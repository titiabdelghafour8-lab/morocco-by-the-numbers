Feature: Price monitor
  As a reader, I want to know what is getting more expensive, where, and whether it is speeding up.
  As the maintainer, I want monthly updates to publish on their own when the text still holds,
  and no forecast unless it has earned its place.

  Scenario: A new month that breaks no claim publishes without review
    Given the published prices data
    And HCP publishes a new month in which headline inflation stays within its claim
    When the sync checks the rebuilt data
    Then the data has changed
    And the sync opens a pull request to publish

  Scenario: A forecast that does not beat the naive benchmark is not shown
    Given back-test errors where the best model is worse than "same change as last year"
    When the page decides whether to publish a forecast
    Then no forecast is published
    And the page says that no model beat the benchmark

  Scenario: A forecast that beats the benchmark is shown with its track record
    Given back-test errors where ETS beats "same change as last year"
    When the page decides whether to publish a forecast
    Then the ETS forecast is published

  Scenario: Contributions explain the headline rate
    Given the published prices data
    Then the contributions of the twelve divisions add up to headline inflation within 0.1 points
