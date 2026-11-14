# Seed data

Synthetic partner order files and reference data for the article's example. Nothing here is real.

- `landing/orders_0601.json`: the approved shape, with `customer_code`.
- `landing/orders_0602.json`: the partner renamed the field to `account_code`, and one amount uses a decimal comma.
- `landing/orders_0603.json`: a mixed file. One record has the old shape; one carries both fields, and they disagree.
- `reference.json`: the approved schema, the customer table, and what the source owner later confirmed: the account-to-customer mapping and the decimal comma.

Amounts arrive as strings, as JSON fields usually do.
