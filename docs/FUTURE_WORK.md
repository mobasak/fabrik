# Fabrik Future Work

**Created:** 2025-12-23  
**Status:** Backlog items for future development

---

## Priority 1: Integrate with Existing Apps (2-4 hours)

Add file upload capability to existing services.

### YouTube Pipeline
```python
# Replace local storage with R2
from fabrik.drivers import R2Client

r2 = R2Client()
r2.put_object(f"youtube/{video_id}/audio.mp3", audio_data, "audio/mpeg")
```

### Translator Service
- Document upload for translation
- Store original + translated versions
- Presigned download URLs

### Implementation Steps
1. Add R2Client to service dependencies
2. Replace `open(file, 'wb')` with `r2.put_object()`
3. Replace `open(file, 'rb')` with `r2.get_object()`
4. Update API to return presigned download URLs

---

## Priority 2: Build Upload UI Component (4 hours)

React/Next.js component for drag-drop file uploads.

### Features
- Drag and drop zone
- File type validation
- Progress bar during upload
- Preview for images
- Cancel upload
- Retry on failure

### Tech Stack
- React + TypeScript
- TailwindCSS for styling
- Direct upload to R2 via presigned URL

### Code Skeleton
```tsx
// components/FileUpload.tsx
export function FileUpload({ 
  onUpload, 
  allowedTypes = ['application/pdf', 'audio/*'],
  maxSize = 100 * 1024 * 1024 
}) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  
  const handleUpload = async (file: File) => {
    // 1. Get presigned URL from API
    // 2. Upload directly to R2
    // 3. Confirm upload
    // 4. Call onUpload with file metadata
  };
  
  return (
    <div className="border-2 border-dashed rounded-lg p-8">
      {/* Drop zone UI */}
    </div>
  );
}
```

---

## Priority 3: Enable Transcription (2 hours)

Connect Soniox API to file-worker for audio transcription.

### Soniox Integration
```python
# worker/processors/transcribe.py
import requests

SONIOX_API_KEY = os.environ['SONIOX_API_KEY']

def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio file using Soniox API."""
    with open(audio_path, 'rb') as f:
        response = requests.post(
            'https://api.soniox.com/v1/transcribe',
            headers={'Authorization': f'Bearer {SONIOX_API_KEY}'},
            files={'audio': f}
        )
    return response.json()['text']
```

### Credentials Available
```bash
# In /opt/fabrik/.env
SONIOX_API_KEYS=3f8a46880a882de1b8707f2e34a0e413b9b91dea36a3753e08c8d5a786f91273,...
```

### Job Flow
1. File uploaded → status: `pending`
2. Job created: `job_type: transcribe`
3. Worker claims job
4. Downloads audio from R2
5. Calls Soniox API
6. Uploads transcript to R2 as derivative
7. Updates job status: `completed`

---

## Priority 4: Build Admin Dashboard (2 days)

Web UI to manage Fabrik deployments.

### Features
- List all deployed apps
- View deployment status
- Trigger new deployments
- View logs
- Manage secrets
- Monitor resource usage

### Tech Stack
- Next.js 14 (App Router)
- TailwindCSS + shadcn/ui
- Supabase Auth (admin only)
- Real-time updates via Supabase Realtime

### Pages
```
/dashboard
├── /apps              # List all deployed apps
│   └── /[id]          # App details, logs, config
├── /templates         # Available templates
├── /files             # File storage browser
│   └── /[id]          # File details, derivatives
├── /jobs              # Processing job queue
└── /settings          # API keys, config
```

### Database Tables Needed
```sql
-- Track deployments
CREATE TABLE deployments (
    id UUID PRIMARY KEY,
    app_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    logs TEXT,
    error TEXT
);

-- Track app configurations
CREATE TABLE app_configs (
    id UUID PRIMARY KEY,
    app_id TEXT UNIQUE NOT NULL,
    spec JSONB NOT NULL,
    last_deployed_at TIMESTAMPTZ,
    coolify_uuid TEXT
);
```

---

## Lower Priority Items

### WordPress Template
- One-click WordPress deployment
- WP-CLI integration for plugin installation
- Auto-configure security plugins

### Cloudflare DNS Driver
- Alternative to Namecheap
- Faster propagation
- Better API

### Auto-scaling Workers
- Monitor job queue length
- Spin up additional workers when needed
- Scale down during idle periods

### Deployment Webhooks
- Notify on deployment success/failure
- Slack/Discord integration
- Email notifications

### GitHub Actions Integration
- Auto-deploy on push to main
- Preview deployments for PRs
- Rollback capability

---

## Notes

- All credentials stored in `/opt/fabrik/.env`
- Test user: `test@fabrik.dev` / `FabrikTest2025!`
- Test tenant: `test-tenant` (ID: `9f814814-e08f-40fb-82ea-4e1fb3b5a31d`)
