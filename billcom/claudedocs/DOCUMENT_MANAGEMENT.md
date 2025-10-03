# Bill.com Document Management

## Overview

This feature allows users to upload, download, and manage documents attached to vendor bills in Bill.com. Documents can be PDFs, images, or other file types supported by Bill.com (up to 6 MB per file).

## Features Implemented

### 1. Document Model (`billcom.document`)

**File**: `models/billcom_document.py`

New model for managing Bill.com documents with the following features:

- **File Management**: Upload files up to 6 MB
- **Upload Status Tracking**: pending → in_progress → uploaded/failed
- **Download from Bill.com**: Retrieve previously uploaded documents
- **Chatter Integration**: Activity tracking and notifications
- **Error Handling**: User-friendly error messages

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| name | Char | Document name with extension (e.g., invoice.pdf) |
| bill_id | Many2one | Related vendor bill (account.move) |
| billcom_id | Char | Bill.com document ID (starts with 00h when uploaded) |
| billcom_upload_id | Char | Temporary upload ID (starts with 0du during upload) |
| file_data | Binary | File content stored in Odoo |
| file_size | Integer | File size in bytes |
| download_link | Char | Download URL from Bill.com |
| upload_status | Selection | pending/in_progress/uploaded/failed |
| error_message | Text | Error details if upload fails |
| created_time | Datetime | Document creation time in Bill.com |

### 2. File Upload Workflow

**API Endpoint**: `POST /v3/documents/bills/{billId}?name={filename}`

**Implementation**: `button_upload_to_billcom()`

#### Upload Process

1. **Validation**:
   - Check bill is synced to Bill.com (has `billcom_id`)
   - Verify file size ≤ 6 MB
   - Ensure file content exists

2. **Upload**:
   - Send file as `application/octet-stream`
   - Include filename in query parameter
   - Set status to `in_progress`

3. **Response Handling**:
   - **Upload Complete**: `id` starts with `00h` → status = `uploaded`
   - **Upload In Progress**: `uploadId` starts with `0du` → status = `in_progress`
   - **Error**: Extract friendly message → status = `failed`

4. **Chatter Notification**:
   - Post upload status to bill's chatter
   - Include document name, file size, and Bill.com ID

#### Example Upload

```python
# User uploads invoice.pdf (2.5 MB) to a synced bill

# 1. Document created in Odoo
document = env['billcom.document'].create({
    'name': 'invoice.pdf',
    'bill_id': bill.id,
    'file_data': base64_encoded_content,
})

# 2. User clicks "Upload to Bill.com"
document.button_upload_to_billcom()

# 3. Upload completes
# Result:
# - billcom_id = '00h1234567890'
# - upload_status = 'uploaded'
# - download_link = 'https://...'
# - file_size = 2621440 (bytes)

# 4. Chatter message posted to bill
```

### 3. Upload Status Checking

**API Endpoint**: `GET /v3/documents/upload-status?ids={uploadId}`

**Implementation**: `button_check_upload_status()`

For documents with `upload_status = 'in_progress'`, this button:
1. Queries Bill.com for upload status
2. If status = `UPLOADED`:
   - Fetches document details with `GET /v3/documents/{documentId}`
   - Updates `billcom_id`, `download_link`, `created_time`
   - Sets status to `uploaded`
   - Posts success to chatter
3. If status = `IN_PROGRESS`:
   - Shows notification to check again later

### 4. Document Download

**API Endpoint**: Download link from document response

**Implementation**: `button_download_from_billcom()`

Downloads document from Bill.com using the `download_link`:

```bash
curl '{downloadLink}' \
  --header 'sessionId: {session_id}' \
  --header 'devKey: {dev_key}' \
  --output document.pdf
```

**Process**:
1. Validate `download_link` exists
2. Download file using authenticated request
3. Update `file_data` in Odoo
4. Show success notification

### 5. Automatic Document Sync

**Implementation**: `sync_documents_from_billcom(bill)`

**API Endpoint**: `GET /v3/documents/bills/{billId}?max=100`

Fetches all documents for a bill from Bill.com:

```python
service = env['billcom.service']
env['billcom.document'].sync_documents_from_billcom(bill)
# Creates/updates document records in Odoo
# Posts summary to bill chatter
```

**Response Format**:
```json
[
  {
    "id": "00h1234567890",
    "name": "invoice.pdf",
    "downloadLink": "https://...",
    "createdTime": "2025-10-03T10:30:00Z"
  }
]
```

## Bill.com API Integration

### Enhanced `_make_request()` Method

**File**: `models/billcom_service_abstract.py`

Added support for file uploads with new parameter:

```python
def _make_request(
    self,
    endpoint,
    method="GET",
    data=None,
    params=None,
    extra_headers=None,
    is_file_upload=False  # NEW
):
```

**File Upload Behavior**:
- When `is_file_upload=True`:
  - `data` should be bytes (not dict)
  - Content-Type: `application/octet-stream`
  - Timeout: 60 seconds (vs 30 for JSON)
  - Uses `_send_file_upload_request()`

### New Methods

#### `_execute_request_with_upload()`

Handles file upload requests with special content type:

```python
headers["content-type"] = "application/octet-stream"
response = requests.post(
    url,
    data=file_binary,  # Raw bytes
    headers=headers,
    params=params,
    timeout=60
)
```

#### `_send_file_upload_request()`

Sends HTTP POST/PUT with binary data:
- Supports POST and PUT methods
- Longer timeout for large files
- Passes file data directly (not JSON)

#### `_download_document()`

Downloads document from Bill.com:

```python
file_data = service._download_document(download_link)
# Returns: bytes
```

**Error Handling**:
- 401: Token expired → refresh and retry
- 403: Permission denied
- 404: Document not found

## User Interface

### Bill Form View Enhancement

**File**: `views/account_move_views.xml`

Added document list to Bill.com Integration tab:

```xml
<field name="billcom_document_ids" context="{'default_bill_id': active_id}">
    <tree editable="bottom">
        <field name="name" />
        <field name="file_data" filename="name" widget="binary" />
        <field name="file_size" widget="integer" readonly="1" />
        <field name="upload_status" widget="badge" />
        <button name="button_upload_to_billcom" ... />
        <button name="button_check_upload_status" ... />
        <button name="button_download_from_billcom" ... />
    </tree>
</field>
```

**Features**:
- Inline editing for quick document addition
- Color coding: green (uploaded), red (failed), orange (in progress)
- Action buttons: Upload, Check Status, Download
- File preview and download

### Standalone Document View

**File**: `views/billcom_document_views.xml`

- **Tree View**: List all documents with filtering and grouping
- **Form View**: Full document details with chatter
- **Search View**: Filter by status, bill, or Bill.com ID

**Menu Location**: Bill.com → From Bill.com → Documents

## Workflow Examples

### Example 1: Upload New Document

**Scenario**: User wants to attach an invoice PDF to a synced bill

1. Open vendor bill in Odoo
2. Go to "Bill.com Integration" tab
3. Click "Add a line" in documents section
4. Enter document name: `supplier_invoice.pdf`
5. Upload file using file picker
6. Click "Upload to Bill.com" button
7. **Result**:
   - Status shows "Uploaded" with green badge
   - Bill.com document ID displayed
   - Chatter message: "Bill.com Document Upload Completed"

### Example 2: Monitor Upload Progress

**Scenario**: Large file upload takes time to process

1. Upload 5 MB PDF file
2. Status shows "Upload In Progress" (orange badge)
3. Click "Check Upload Status" button
4. If still processing: notification "Upload is still in progress"
5. After ~2 minutes, click again
6. **Result**:
   - Status changes to "Uploaded" (green)
   - Download link becomes available
   - Chatter updated with completion message

### Example 3: Download Document from Bill.com

**Scenario**: Document was uploaded via Bill.com web interface

1. Sync bill from Bill.com (webhook or manual)
2. System auto-creates document records
3. Document shows "Uploaded" status but no file data in Odoo
4. Click "Download from Bill.com" button
5. **Result**:
   - File downloaded and stored in Odoo
   - File size updated
   - File available for download in Odoo

### Example 4: Handle Upload Error

**Scenario**: File exceeds 6 MB limit

1. Try to upload 7 MB file
2. **Result**:
   - Popup error: "File size exceeds Bill.com limit of 6 MB. Current size: 7.00 MB"
   - Status remains "Pending Upload"
   - User must compress or split file

### Example 5: Sync All Documents

**Scenario**: Bill has 3 documents in Bill.com, none in Odoo

```python
# Via webhook or scheduled action
bill = env['account.move'].browse(bill_id)
env['billcom.document'].sync_documents_from_billcom(bill)

# Result:
# - 3 document records created in Odoo
# - All marked as "uploaded"
# - Download links available
# - Chatter: "Synced 3 document(s) from Bill.com"
```

## Error Handling

### File Size Validation

**Error**: File > 6 MB

**Message**:
```
File size exceeds Bill.com limit of 6 MB.
Current size: 7.50 MB
```

**User Action**: Compress or split file before upload

### Bill Not Synced

**Error**: Bill missing `billcom_id`

**Message**:
```
Cannot upload document: Bill must be synced to Bill.com first.

Please sync the bill using the 'Sync to Bill.com' button.
```

**User Action**: Sync bill to Bill.com before uploading documents

### Upload Failure

**Error**: Network error, API error, validation error

**Behavior**:
1. Status set to `failed`
2. Error message stored in `error_message` field
3. Friendly error shown in popup
4. Chatter message with error details
5. User can retry upload after fixing issue

### Download Failure

**Error**: Document no longer exists (404)

**Message**:
```
Failed to download document from Bill.com:

• Not Found - Document no longer exists
```

**User Action**: Document may have been deleted in Bill.com

## API Reference

### Upload Document

```
POST /v3/documents/bills/{billId}?name={filename}
Content-Type: application/octet-stream
Body: <binary file data>

Response:
{
  "id": "00h1234567890",  // or uploadId: "0du9876543210"
  "name": "invoice.pdf",
  "downloadLink": "https://...",
  "createdTime": "2025-10-03T10:30:00Z"
}
```

### Get Upload Status

```
GET /v3/documents/upload-status?ids=0du9876543210

Response:
[
  {
    "uploadId": "0du9876543210",
    "status": "UPLOADED" | "IN_PROGRESS",
    "documentId": "00h1234567890"  // when UPLOADED
  }
]
```

### List Bill Documents

```
GET /v3/documents/bills/{billId}?max=100&page={nextPage}

Response:
[
  {
    "id": "00h1234567890",
    "name": "invoice.pdf",
    "downloadLink": "https://...",
    "createdTime": "2025-10-03T10:30:00Z"
  }
]
```

### Download Document

```
GET {downloadLink}
Headers:
  sessionId: {session_id}
  devKey: {dev_key}

Response: Binary file data
```

## Security

**File**: `security/ir.model.access.csv`

Access rules:
- **Invoice Users** (account.group_account_invoice): Read, Write, Create
- **Accounting Managers** (account.group_account_manager): Full access including Delete

## Database Schema

```sql
-- New table: billcom_document
CREATE TABLE billcom_document (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    bill_id INTEGER REFERENCES account_move(id) ON DELETE CASCADE,
    billcom_id VARCHAR,
    billcom_upload_id VARCHAR,
    file_data BYTEA,
    file_size INTEGER,
    download_link VARCHAR,
    upload_status VARCHAR,
    error_message TEXT,
    created_time TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    create_date TIMESTAMP,
    write_date TIMESTAMP,
    create_uid INTEGER,
    write_uid INTEGER
);

-- New field in account_move
ALTER TABLE account_move
ADD COLUMN billcom_document_ids INTEGER[];  -- Virtual One2many
```

## Testing Recommendations

### Test 1: Basic Upload

1. Create vendor bill
2. Sync to Bill.com
3. Add document (< 6 MB)
4. Upload to Bill.com
5. ✅ Verify status = uploaded
6. ✅ Verify billcom_id present
7. ✅ Verify chatter message

### Test 2: Large File Upload

1. Add 5 MB file
2. Upload to Bill.com
3. ✅ Verify status = in_progress
4. Wait 2 minutes
5. Click "Check Upload Status"
6. ✅ Verify status = uploaded

### Test 3: File Size Limit

1. Try upload 7 MB file
2. ✅ Verify error popup
3. ✅ Verify upload prevented

### Test 4: Bill Not Synced

1. Create new bill (not synced)
2. Add document
3. Try upload
4. ✅ Verify error about syncing bill first

### Test 5: Download Document

1. Upload document to Bill.com
2. Delete file_data from Odoo
3. Click "Download from Bill.com"
4. ✅ Verify file downloaded
5. ✅ Verify file_data populated

### Test 6: Sync From Bill.com

1. Upload 2 documents via Bill.com web
2. Call `sync_documents_from_billcom(bill)`
3. ✅ Verify 2 document records created
4. ✅ Verify chatter message

### Test 7: Multiple Documents

1. Add 3 documents to same bill
2. Upload all
3. ✅ Verify all uploaded
4. ✅ Verify distinct billcom_id values

## Performance Considerations

### File Size and Upload Time

| File Size | Upload Time | Status Check |
|-----------|-------------|--------------|
| < 1 MB | Immediate | Not needed |
| 1-3 MB | < 30 seconds | Optional |
| 3-6 MB | 1-3 minutes | Recommended |

### Timeouts

- **JSON requests**: 30 seconds
- **File uploads**: 60 seconds
- **Downloads**: 60 seconds

### Pagination

For bills with many documents:
- Max 100 documents per request
- Use `page` parameter for next page
- Implement if needed in future

## Integration with ir.attachment

### Overview

The `billcom.document` model is now fully integrated with Odoo's native `ir.attachment` system, enabling:
- Automatic creation of attachments when downloading from Bill.com
- Upload of existing attachments to Bill.com
- Two-way synchronization between attachments and documents

### Attachment Creation (Download from Bill.com)

**When syncing or downloading documents from Bill.com**, the system automatically:

1. Downloads file content from Bill.com
2. Stores it in `billcom.document.file_data`
3. Creates/updates `ir.attachment` record:
   - Links to bill (`res_model='account.move'`, `res_id=bill.id`)
   - Sets proper mimetype based on filename
   - Updates description with Bill.com ID

**Implementation**: `models/billcom_document.py:364`

```python
def _create_or_update_attachment(self, file_data_encoded):
    """Create or update ir.attachment for this document"""
    import mimetypes
    mimetype = mimetypes.guess_type(self.name)[0] or 'application/octet-stream'

    attachment_vals = {
        'name': self.name,
        'datas': file_data_encoded,
        'res_model': 'account.move',
        'res_id': self.bill_id.id,
        'mimetype': mimetype,
        'description': f'Bill.com Document: {self.billcom_id or "pending"}',
    }

    if self.attachment_id:
        self.attachment_id.write(attachment_vals)
    else:
        attachment = self.env['ir.attachment'].create(attachment_vals)
        self.write({'attachment_id': attachment.id})
```

**Called by**:
- `button_download_from_billcom()` - Manual download
- `sync_documents_from_billcom()` - Automatic sync (NEW)

### Document Creation from Existing Attachments

**New Feature**: Convert existing `ir.attachment` records to `billcom.document` records

**Method**: `models/billcom_document.py:466`

```python
@api.model
def create_from_attachment(self, attachment):
    """Create a billcom.document from an ir.attachment"""
    # Validates attachment is linked to vendor bill
    # Checks if document already exists
    # Creates new document with pending upload status
    # Links to original attachment
```

**Validation**:
- Attachment must be linked to `account.move` (vendor bill)
- Bill must be `move_type='in_invoice'`
- Prevents duplicate document creation

**Button**: `models/account_move.py:305`

```python
def button_sync_attachments_to_billcom(self):
    """Create billcom.document records from existing ir.attachment records"""
    # Finds all attachments for this bill
    # Creates document for each attachment
    # Posts summary to chatter
    # Shows notification with count
```

**UI Location**: Bill.com Integration tab → "Create Documents from Attachments" button

### Workflow Examples

#### Example 1: Sync Documents from Bill.com (Auto-Creates Attachments)

**Scenario**: Documents uploaded via Bill.com web interface

1. User syncs bill from Bill.com (webhook or manual)
2. System calls `sync_documents_from_billcom(bill)`
3. For each document in Bill.com:
   - Creates `billcom.document` record
   - **NEW**: Auto-downloads file content
   - **NEW**: Creates `ir.attachment` automatically
4. **Result**:
   - Documents visible in Bill.com Documents section
   - Attachments visible in Odoo's attachment sidebar
   - Files ready for download in Odoo

**Code**: `models/billcom_document.py:516-532`

```python
# Auto-download and create attachment for newly synced documents
try:
    if document.download_link:
        file_data = service._download_document(document.download_link)
        if file_data:
            file_data_encoded = base64.b64encode(file_data)
            document.write({'file_data': file_data_encoded})
            document._create_or_update_attachment(file_data_encoded)
except Exception as e:
    _logger.warning("Failed to auto-download document %s: %s", doc_id, str(e))
```

#### Example 2: Upload Existing Attachments to Bill.com

**Scenario**: Bill already has attachments in Odoo, need to upload to Bill.com

1. Open vendor bill in Odoo
2. Go to Bill.com Integration tab
3. Click "Create Documents from Attachments" button
4. System finds all attachments for this bill
5. Creates `billcom.document` record for each
6. **Result**:
   - New documents appear in list with "pending" status
   - Click "Upload" on each to send to Bill.com
   - Chatter message: "Created 3 new Bill.com document(s) from 3 attachment(s)"

**Example**:
```
Bill has 3 attachments:
- invoice.pdf (uploaded by user)
- receipt.jpg (scanned via mobile)
- contract.pdf (from email)

After clicking "Create Documents from Attachments":
- 3 billcom.document records created
- Each linked to its source attachment
- Each in "pending" status
- Ready to upload to Bill.com
```

#### Example 3: Two-Way Sync

**Scenario**: Document downloaded from Bill.com, then modified locally

1. Sync document from Bill.com → creates attachment
2. User downloads file from Odoo attachment
3. User modifies file locally
4. User uploads modified file to same attachment
5. System updates `billcom.document.file_data` (planned enhancement)
6. User clicks "Upload to Bill.com" to sync changes

### Database Schema Updates

**New field in billcom.document**:
```sql
ALTER TABLE billcom_document
ADD COLUMN attachment_id INTEGER REFERENCES ir_attachment(id);
```

**Relationship**:
- `billcom.document.attachment_id` → `ir.attachment.id` (Many2one)
- One document can link to one attachment
- One attachment can have multiple documents (if bill is duplicated)

### UI Changes

**Bill Form View** (`views/account_move_views.xml:39-50`):

Added button above document list:
```xml
<button
    name="button_sync_attachments_to_billcom"
    string="Create Documents from Attachments"
    type="object"
    class="btn-secondary"
    icon="fa-paperclip"
    help="Create Bill.com document records from existing attachments on this bill"
/>
```

**Document List** (no changes):
- Still shows upload/download buttons
- Status badges remain same
- Inline editing preserved

### Testing Recommendations

#### Test 1: Auto-Create Attachment on Sync

1. Upload document via Bill.com web interface
2. Sync bill from Bill.com in Odoo
3. ✅ Verify `billcom.document` created
4. ✅ Verify `ir.attachment` created and linked
5. ✅ Verify file downloadable from attachment sidebar
6. ✅ Verify mimetype correct

#### Test 2: Create Documents from Existing Attachments

1. Create vendor bill in Odoo
2. Upload 2 files via attachment sidebar
3. Click "Create Documents from Attachments"
4. ✅ Verify 2 `billcom.document` records created
5. ✅ Verify both linked to attachments
6. ✅ Verify both in "pending" status
7. Click "Upload" on each document
8. ✅ Verify upload to Bill.com succeeds

#### Test 3: Prevent Duplicate Documents

1. Create attachment on bill
2. Click "Create Documents from Attachments" → 1 document created
3. Click button again
4. ✅ Verify no duplicate document created
5. ✅ Verify chatter message shows "0 new, 1 existing"

#### Test 4: Attachment Update on Download

1. Create document and upload to Bill.com
2. Delete `file_data` from document
3. Delete linked `ir.attachment`
4. Click "Download from Bill.com"
5. ✅ Verify file downloaded
6. ✅ Verify new `ir.attachment` created
7. ✅ Verify attachment linked to document

#### Test 5: Validation Errors

1. Try to create document from attachment linked to customer invoice
2. ✅ Verify error: "Attachment must be linked to a vendor bill"
3. Try with attachment linked to different model
4. ✅ Verify error: "Attachment must be linked to a vendor bill"

### Performance Considerations

**Auto-Download on Sync**:
- Downloads happen during sync (may slow down sync)
- Each document downloaded individually
- Failed downloads logged but don't stop sync
- Consider batch download for bills with many documents

**Attachment Creation**:
- Creates one `ir.attachment` per document
- Uses Odoo's standard attachment storage (filestore or database)
- Mimetype guessed from filename
- No impact on Bill.com API quota

### Future Enhancements

### Suggested Improvements

1. **Bulk Upload**: Upload multiple documents at once
2. **Drag & Drop**: UI for easier document addition
3. **Document Preview**: Show PDF/image preview in Odoo
4. **OCR Integration**: Extract data from uploaded documents
5. **Scheduled Sync**: Auto-sync documents from Bill.com
6. **Document Types**: Categorize documents (invoice, receipt, contract)
7. **Version Control**: Track document versions
8. **Approval Workflow**: Require approval before upload
9. **Batch Download**: Download all documents for bill in one operation (RECOMMENDED)
10. **Attachment Monitor**: Watch for attachment changes and sync to Bill.com automatically

## Troubleshooting

### Issue: Status Stuck at "In Progress"

**Cause**: Bill.com processing delay or network error

**Solution**:
1. Wait 5 minutes
2. Click "Check Upload Status"
3. If still stuck after 10 minutes, check Bill.com web interface
4. If uploaded in Bill.com but status wrong in Odoo:
   ```python
   document.write({
       'upload_status': 'uploaded',
       'billcom_id': '{id_from_billcom}'
   })
   ```

### Issue: Download Link Expired

**Cause**: Download links expire after certain time

**Solution**: Sync documents again to get fresh links

### Issue: Upload Fails with 400 Error

**Cause**: Invalid filename or missing extension

**Solution**: Ensure filename includes extension (e.g., `.pdf`, `.jpg`)

## Conclusion

The Bill.com document management feature provides:
- ✅ Complete document upload workflow
- ✅ Upload status tracking
- ✅ Document download capability
- ✅ User-friendly error handling
- ✅ Chatter integration
- ✅ Sync from Bill.com

**Impact**: Users can now manage bill documents entirely within Odoo, with full synchronization to Bill.com.
