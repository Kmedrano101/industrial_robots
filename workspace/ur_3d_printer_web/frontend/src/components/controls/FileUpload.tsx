import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { useApiUpload } from '../../hooks/useApi';
import { MAX_UPLOAD_SIZE } from '../../lib/constants';
import Card from '../common/Card';
import Button from '../common/Button';

interface UploadRes {
  filepath: string;
  filename: string;
  size: number;
  file_type: string;
  bounding_box: Record<string, number> | null;
  triangle_count: number | null;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileUpload() {
  const { t } = useTranslation();
  const { setUploadedFile, setIsUploading, uploadedFile, isUploading } = usePrintStore();
  const upload = useApiUpload<UploadRes>('/upload');

  const onDrop = useCallback(
    async (files: File[]) => {
      const file = files[0];
      if (!file) return;

      setIsUploading(true);
      const res = await upload.execute(file);
      setIsUploading(false);

      if (res) {
        setUploadedFile({
          filepath: res.filepath,
          filename: res.filename,
          size: res.size,
          boundingBox: res.bounding_box,
          triangleCount: res.triangle_count,
        });
      }
    },
    [upload, setUploadedFile, setIsUploading],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'model/stl': ['.stl'] },
    maxSize: MAX_UPLOAD_SIZE,
    multiple: false,
  });

  if (!uploadedFile) {
    return (
      <Card>
        <div
          {...getRootProps()}
          className={`cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
            isDragActive ? 'border-accent bg-accent/10' : 'border-line hover:border-accent/60 hover:bg-surface2/60'
          }`}
        >
          <input {...getInputProps()} />
          <svg className="mx-auto mb-2 h-9 w-9 text-faint" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className="text-sm font-medium">
            {isDragActive ? t('upload.dropzoneActive') : t('upload.dropzone')}
          </p>
          <p className="mt-1 text-xs text-faint">{t('upload.supported')} · {t('upload.maxSize')}</p>
          {isUploading && <p className="mt-2 text-sm text-accent">{t('upload.uploading')}</p>}
          {upload.error && <p className="mt-2 text-sm text-danger">{upload.error}</p>}
        </div>
      </Card>
    );
  }

  const bb = uploadedFile.boundingBox;
  return (
    <Card
      title={t('upload.loaded')}
      action={
        <Button
          size="sm"
          variant="ghost"
          onClick={() => usePrintStore.getState().reset()}
          aria-label={t('upload.remove')}
          title={t('upload.remove')}
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          }
        />
      }
    >
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
          </svg>
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium" title={uploadedFile.filename}>{uploadedFile.filename}</p>
          <p className="mt-0.5 text-xs text-muted">
            {formatSize(uploadedFile.size)}
            {uploadedFile.triangleCount ? ` · ${t('upload.triangles', { count: uploadedFile.triangleCount })}` : ''}
          </p>
          {bb && (
            <p className="mt-0.5 font-mono text-xs text-muted">
              {(bb.x_max - bb.x_min).toFixed(1)} × {(bb.y_max - bb.y_min).toFixed(1)} × {(bb.z_max - bb.z_min).toFixed(1)} mm
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
