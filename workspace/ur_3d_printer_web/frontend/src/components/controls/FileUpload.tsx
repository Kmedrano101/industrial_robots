import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { useApiUpload } from '../../hooks/useApi';
import { MAX_UPLOAD_SIZE } from '../../lib/constants';
import Card from '../common/Card';

interface UploadRes {
  filepath: string;
  filename: string;
  size: number;
  file_type: string;
  bounding_box: Record<string, number> | null;
  triangle_count: number | null;
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

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <Card>
      {!uploadedFile ? (
        <div
          {...getRootProps()}
          className={`cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
            isDragActive
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-950'
              : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
          }`}
        >
          <input {...getInputProps()} />
          <svg className="mx-auto h-10 w-10 text-gray-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className="text-sm">
            {isDragActive ? t('upload.dropzoneActive') : t('upload.dropzone')}
          </p>
          <p className="mt-1 text-xs text-gray-400">{t('upload.supported')} · {t('upload.maxSize')}</p>
          {isUploading && <p className="mt-2 text-sm text-blue-500">Uploading...</p>}
          {upload.error && (
            <p className="mt-2 text-sm text-red-500">{upload.error}</p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium truncate">
              {t('upload.fileInfo', { name: uploadedFile.filename, size: formatSize(uploadedFile.size) })}
            </p>
            <button
              onClick={() => usePrintStore.getState().reset()}
              className="text-xs text-gray-400 hover:text-red-500"
            >
              ✕
            </button>
          </div>
          {uploadedFile.triangleCount && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {t('upload.triangles', { count: uploadedFile.triangleCount })}
            </p>
          )}
          {uploadedFile.boundingBox && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {t('upload.boundingBox', {
                x: (uploadedFile.boundingBox.x_max - uploadedFile.boundingBox.x_min).toFixed(1),
                y: (uploadedFile.boundingBox.y_max - uploadedFile.boundingBox.y_min).toFixed(1),
                z: (uploadedFile.boundingBox.z_max - uploadedFile.boundingBox.z_min).toFixed(1),
              })}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
