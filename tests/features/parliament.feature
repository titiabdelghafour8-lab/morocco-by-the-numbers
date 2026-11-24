Feature: What parliament asks about
  As a reader, I want to know what MPs ask the government about and how that has changed.
  As the maintainer, I want no MP named anywhere, and topic names that only change when I review them.

  Scenario: No published file names a member of parliament
    Given a list of members' names
    And a topic whose representative questions include one that names a member
    When the parliament page data is built
    Then no published parliament file contains any member's name
    And the topic still shows its other representative questions

  Scenario: A topic label never changes without a reviewed labels file
    Given topic labels reviewed for the current topic model
    When the topic model is rerun and its topics change
    Then building the parliament page fails and asks for the labels to be reviewed

  Scenario: Every topic is named in Arabic, French and English
    Given the reviewed topic labels
    Then every topic has a name in Arabic, French and English

  Scenario: Shares by year add up
    Given the published parliament data
    Then each year's topic shares add up to 100%
