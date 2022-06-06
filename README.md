# Automated TelQ Reporting

Automated Reporting for SMS Delivery via TelQ

This script is intended to run as an AWS lambda function, configured via terraform.

## Function
This script functions as two distinct lambda functions:  
1. The test trigger function - test_handler.py
2. The test result function - results_handler.py

The trigger function creates the tests in TelQ, receives the pertinent information in response, and triggers *** to send the required SMS messages for each of these tests. Once completed, it stores the TelQ test IDs in a DynamoDB table for later retrieval.

The result function pulls the list of TelQ test IDs stored previously in the DynamoDB, queries TelQ for the test results of each, and builds a table of that information before finally emailing that table to the specified recipients.
## Code Structure
The following files are unique to this script:
- **results_handler.py**
  - Obtain results and email them
- **test_handler.py**
  - trigger tests and send SMSs

## Customizing Script
For the trigger function, within the start of the "main" function are three fields that can be changed as needed:
- Target Countries
- Target Networks/Carriers
- Number of tests per Network/Carrier

These must be formatted as lists/dictionaries. It's mandatory that the target countries matches the keys in the target networks and that everything is kept lowercase.

For the report function, within the start of the "main" function are several fields that can be changed as needed:
- report_name - The name of the report.
- smtp_server - Mail server to send from. Best not to change this.
- field_list - Ordered list of fields to display in the email/CSV file.
- results_in_email - Weather or not to include any results in the email body.
- attach_csv - Weather or not to include a CSV file with the results.
- results_in_email_count - How many results to show in the email body.
  - Set to "0" to include ALL results.
  - Set to some small number and this functions like a "preview"
- testing_mode - Used for testing. Output is printed rather than emailed.
- email_from - From address for the report email
- email_to - List of emails to send the report to.
- unique_table_name - The name of the DynamoDB table unique to this report.

## Requirements
This script relies on the presence of the following external python modules:
- requests
- boto3