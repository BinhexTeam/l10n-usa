# Bill.com Partner Matching Wizard

## 📋 Overview

The Partner Matching Wizard helps you homologate (link) existing partners between Odoo and Bill.com when both systems already have vendor/customer records. This is essential for production environments where data was entered independently in both systems.

## 🎯 Purpose

When you have:
- Vendors already created in Odoo
- Vendors already created in Bill.com
- No `billcom_id` linking them together

This wizard analyzes both datasets and suggests matches based on multiple criteria.

## 🔍 Matching Algorithm

The wizard uses a **3-criteria matching system**:

### Criteria (in order of evaluation):

1. **Email**: Exact match (case-insensitive, normalized)
2. **Phone**: Exact match (digits only, ignores formatting)
3. **Name**: Exact match (case-insensitive, no accents, no special characters)

### Confidence Levels:

| Confidence | Criteria Matched | Description |
|------------|------------------|-------------|
| **High (3/3)** | Email + Phone + Name | All three criteria match - safe for auto-linking |
| **Medium (2/3)** | Any two criteria | Two criteria match - review recommended |
| **Low (1/3)** | Any one criterion | One criterion matches - manual review required |
| **None (0/3)** | No criteria | No match found - manual search needed |

## 🚀 Usage

### Step 1: Access the Wizard

Navigate to:
```
Bill.com → Configuration → Partner Matching
```

### Step 2: Select Partner Type

Choose:
- **Vendors**: Match supplier partners
- **Customers**: Match customer partners

### Step 3: Configure Options

- **Auto-link high confidence (3/3)**:
  - ✓ Check to automatically link perfect matches
  - ✗ Uncheck to manually review all matches

### Step 4: Find Matches

Click **"Find Matches"** button:
- Wizard fetches all Odoo partners without `billcom_id`
- Fetches all Bill.com vendors/customers
- Analyzes and scores each potential match
- Displays results grouped by confidence level

### Step 5: Review Matches

Review the matching results in tabs:
- **All Matches**: Complete list
- **High Confidence (3/3)**: Perfect matches
- **Medium Confidence (2/3)**: Good matches needing review
- **Low Confidence (1/3)**: Weak matches requiring caution
- **No Matches**: Partners without any match

### Step 6: Select Actions

For each match, choose:
- **Link**: Apply this match
- **Ignore**: Skip this partner
- **Review**: Mark for later decision

You can also:
- **Link Now**: Immediately link a specific partner
- **Unlink**: Remove an incorrect link

### Step 7: Apply Selected Links

Click **"Apply Selected Links"** to:
- Link all partners marked with "Link" action
- Update Odoo partners with Bill.com IDs
- Create audit trail in partner chatter
- Display success summary

## 📊 Statistics Dashboard

The wizard shows:
- **Total Partners**: Number of unlinked partners
- **High Confidence**: Count of 3/3 matches
- **Medium Confidence**: Count of 2/3 matches
- **Low Confidence**: Count of 1/3 matches
- **No Matches**: Count of partners without matches

## 🎨 Visual Indicators

Matches are color-coded in the list:
- 🟢 **Green**: High confidence (3/3)
- 🔵 **Blue**: Medium confidence (2/3)
- 🟠 **Orange**: Low confidence (1/3)
- ⚪ **Gray**: No match (0/3)
- **Bold**: Already linked

## ✅ Best Practices

### Before Starting:
1. ✓ Ensure Bill.com API is configured and connected
2. ✓ Verify vendor/customer sync is enabled
3. ✓ Backup your database (or create a snapshot)
4. ✓ Review a sample of data for data quality issues

### During Matching:
1. ✓ Start with "High Confidence" matches
2. ✓ Carefully review "Medium Confidence" matches
3. ✓ Be cautious with "Low Confidence" matches
4. ✓ Check for duplicates in either system
5. ✓ Verify addresses/tax IDs when in doubt

### After Matching:
1. ✓ Review linked partners in partner list
2. ✓ Check audit trail in partner chatter
3. ✓ Test syncing a document to verify link
4. ✓ Document any manual corrections needed

## 🔧 Troubleshooting

### Problem: No matches found
**Possible causes:**
- Different naming conventions (e.g., "Inc." vs "Incorporated")
- Missing email/phone in one system
- Data quality issues (typos, formatting)

**Solutions:**
- Improve data quality before matching
- Use Bill.com sync wizard to create new partners instead
- Manually link partners via partner form

### Problem: Too many low-confidence matches
**Possible causes:**
- Generic names (e.g., "Services Company")
- Missing contact information
- Inconsistent data entry

**Solutions:**
- Update missing email/phone fields
- Use more specific partner names
- Consider manual linking for ambiguous cases

### Problem: Wrong match linked
**Solutions:**
- Click "Unlink" button on the matching line
- Correct the data in either system
- Re-run the matching wizard

## 🔒 Security

Access control:
- **Invoice Users**: Can run wizard and view matches
- **Account Managers**: Full access including unlinking

## 📝 Audit Trail

Every link operation creates:
- Chatter message on partner with:
  - Bill.com partner name and ID
  - Confidence level and match details
  - Link method (wizard) and timestamp
- Log entry for troubleshooting

## 🚨 Important Notes

1. **One-way operation**: Linking only updates Odoo → Bill.com reference, doesn't sync data
2. **Reversible**: You can unlink and re-match if needed
3. **No data modification**: Wizard only creates links, doesn't change partner data
4. **Safe to re-run**: Running multiple times won't create duplicates
5. **Webhook-safe**: Links respect `skip_billcom_sync` to prevent loops

## 📚 Related Documentation

- [Bill.com Configuration](./README.md#configuration)
- [Webhook Setup](./README.md#webhooks)
- [Partner Synchronization](./README.md#partner-sync)

## 💡 Tips

1. **Clean data first**: Fix typos and add missing info before matching
2. **Use Tax IDs**: Consider adding Tax ID matching for even higher confidence
3. **Start small**: Test with a small batch before processing all partners
4. **Document decisions**: Use partner notes to record manual decisions
5. **Regular reviews**: Re-run periodically to catch new unlinked partners
