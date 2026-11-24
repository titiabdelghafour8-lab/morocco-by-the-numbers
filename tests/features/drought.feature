Feature: Drought monitor
  As a reader, I want to know how dry it is in the Souss compared with the last
  57 years, and whether less rain explains the river's collapse.
  As the maintainer, I want incomplete records kept out of the index, visibly.

  Scenario: A year with 40 missing days is excluded and flagged
    Given daily rainfall from 1990 to 2010 where hydrological year 2001 has 40 missing days
    When the drought index is computed
    Then hydrological year 2001 has no 12-month SPI
    And hydrological year 2001 is listed as excluded, with 40 missing days

  Scenario: A partial latest year does not count as a drought
    Given daily rainfall from 1990 to 2010 where the last hydrological year stops in December
    When the drought index is computed
    Then the drought series ends in August 2009
    And hydrological year 2010 is listed as excluded

  Scenario: Rain that falls by half halves the predicted river
    Given a river that always carries the same share of the rain
    And rainfall halves after 1999
    When the rain-only model is fitted on 1971 to 1999
    Then rain explains 100% of the river's decline

  Scenario: The water page quotes only numbers that hold
    Given the built water page data
    Then every claim of the water page holds
