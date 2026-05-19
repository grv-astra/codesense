import { Card } from '@/components/atomic/card';
import { Input } from '@/components/atomic/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/atomic/select';
import { useProjectNames } from '@/hooks/use-project';
import { useSbomScan } from '@/hooks/use-scans';
import type { CreateSBOMScanForm } from '@/types/scan';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import {
  AlertCircle,
  CheckCircle2,
  FileJson,
  Play,
  Upload,
  X,
} from 'lucide-react';
import React, { useState } from 'react';

export const Route = createFileRoute('/_authenticated/scan/start/uploadsbom')({
  component: RouteComponent,
});

type FormErrors = Partial<CreateSBOMScanForm & { file_error: string }>;

// ── Shared sub-components (mirror of uploadsbom) ──────────────────────────────

function StepBadge({ step }: { step: number }) {
  return (
    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[11px] font-medium bg-gray-100 dark:bg-white/10 text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-white/10 flex-shrink-0">
      {step}
    </span>
  );
}

function SectionHeading({ step, title }: { step: number; title: string }) {
  return (
    <div className="flex items-center gap-2.5 mb-4">
      <StepBadge step={step} />
      <span className="text-[13px] font-medium text-gray-700 dark:text-gray-300">
        {title}
      </span>
      <div className="flex-1 border-t border-gray-100 dark:border-white/10" />
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-[11px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-1.5">
      {children}
    </label>
  );
}

function ErrorText({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p className="flex items-center gap-1.5 text-[12px] text-red-600 dark:text-red-400 mt-1.5">
      <AlertCircle size={12} />
      {message}
    </p>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

function RouteComponent() {
  const navigate = useNavigate();
  const createScanMutation = useSbomScan();

  const [formData, setFormData] = useState<CreateSBOMScanForm>({
    scan_name: '',
    file: null,
    project_id: '',
  });

  const { data: projects = [] } = useProjectNames();
  const [isDragOver, setIsDragOver] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const clearError = (key: string) =>
    setErrors(prev => ({ ...prev, [key]: undefined }));

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    clearError(name);
  };

  const handleSelectChange = (value: string) => {
    setFormData(prev => ({ ...prev, project_id: value }));
    clearError('project_id');
  };

  const processFile = (file: File) => {
    if (file.type === 'application/json' || file.name.endsWith('.json')) {
      setFormData(prev => ({ ...prev, file }));
      clearError('file_error');
    } else {
      setErrors(prev => ({
        ...prev,
        file_error: 'Please upload a valid SBOM JSON file',
      }));
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  };

  const removeFile = () =>
    setFormData(prev => ({ ...prev, file: null }));

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};
    if (!formData.project_id) newErrors.project_id = 'Please select a project';
    if (!formData.scan_name.trim()) newErrors.scan_name = 'Scan name is required';
    if (!formData.file) newErrors.file_error = 'Please upload a valid SBOM JSON file';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;
    setIsSubmitting(true);
    try {
      await createScanMutation.mutateAsync({
        scan_name: formData.scan_name,
        project_id: formData.project_id,
        file: formData.file,
      });
      setSubmitted(true);
      const projectId = formData.project_id;
      setFormData({ scan_name: '', project_id: '', file: null });
      setTimeout(() => {
        navigate({ from: '/scan/start', to: `../../project/${projectId}` });
      }, 800);
    } catch (error) {
      console.error('Error creating scan:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-8xl mx-auto">

        <Card className="border shadow-sm rounded-xl overflow-hidden">

          {/* Page heading */}
          <div className="px-6">
            <h1 className="text-[22px] font-semibold text-gray-900 dark:text-white leading-tight">
              Start SBOM Scan
            </h1>
            <p className="text-[14px] text-gray-500 dark:text-gray-400 mt-1">
              Upload your SBOM JSON file to begin vulnerability scanning.
            </p>
          </div>

          {/* Accent bar */}
          <div className="h-[3px] w-full bg-gradient-to-r from-[#bf0000] via-[#e03030] to-[#ff6060]" />

          <form onSubmit={handleSubmit} noValidate>
            <div className="px-7 py-6 space-y-7">

              {/* ── Section 1: Project & scan identity ── */}
              <section>
                <SectionHeading step={1} title="Project & scan identity" />

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

                  {/* Project select */}
                  <div>
                    <FieldLabel>Project</FieldLabel>
                    <Select value={formData.project_id} onValueChange={handleSelectChange}>
                      <SelectTrigger
                        className={
                          errors.project_id
                            ? 'border-red-500 dark:border-red-500 bg-red-50 dark:bg-red-900/10'
                            : ''
                        }
                      >
                        <SelectValue placeholder="Select a project…" />
                      </SelectTrigger>
                      <SelectContent>
                        {projects.map(p => (
                          <SelectItem key={p.id} value={p.id}>
                            {p.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <ErrorText message={errors.project_id} />
                  </div>

                  {/* Scan name */}
                  <div>
                    <FieldLabel>Scan name</FieldLabel>
                    <Input
                      name="scan_name"
                      value={formData.scan_name}
                      onChange={handleInputChange}
                      placeholder="e.g. Release v2.4.1 audit"
                      className={[
                        'h-10 text-[14px]',
                        errors.scan_name
                          ? 'border-red-500 dark:border-red-500 bg-red-50 dark:bg-red-900/10'
                          : '',
                      ].join(' ')}
                    />
                    <ErrorText message={errors.scan_name} />
                  </div>
                </div>
              </section>

              {/* Divider */}
              <hr className="border-t border-gray-100 dark:border-white/[0.07]" />

              {/* ── Section 2: SBOM file upload ── */}
              <section>
                <SectionHeading step={2} title="Upload SBOM file" />

                {formData.file ? (
                  /* File preview */
                  (<div className="flex items-center gap-3 p-3.5 rounded-xl border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/[0.02]">
                    <span className="inline-flex items-center justify-center w-9 h-9 rounded-lg bg-[#bf0000]/10 dark:bg-[#bf0000]/20 text-[#bf0000] flex-shrink-0">
                      <FileJson size={15} />
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] font-medium text-gray-800 dark:text-gray-100 truncate">
                        {formData.file.name}
                      </p>
                      <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">
                        {(formData.file.size / (1024 * 1024)).toFixed(2)} MB &mdash; JSON file
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={removeFile}
                      className="flex items-center justify-center w-7 h-7 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-600 transition-colors"
                    >
                      <X size={14} />
                    </button>
                  </div>)
                ) : (
                  /* Drop zone */
                  (<div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={[
                      'relative rounded-xl border-2 border-dashed p-8 text-center transition-all duration-200 cursor-pointer group',
                      isDragOver
                        ? 'border-[#bf0000] bg-[#bf0000]/[0.03] dark:bg-[#bf0000]/[0.06]'
                        : errors.file_error
                        ? 'border-red-400 bg-red-50 dark:bg-red-900/10'
                        : 'border-gray-200 dark:border-white/10 hover:border-gray-300 dark:hover:border-white/20 hover:bg-gray-50 dark:hover:bg-white/[0.02]',
                    ].join(' ')}
                  >
                    <input
                      type="file"
                      accept=".json"
                      onChange={handleFileChange}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    />
                    <span
                      className={[
                        'inline-flex items-center justify-center w-10 h-10 rounded-xl mb-3 transition-colors',
                        isDragOver
                          ? 'bg-[#bf0000] text-white'
                          : 'bg-gray-100 dark:bg-white/[0.07] text-gray-400 group-hover:bg-gray-200 dark:group-hover:bg-white/10',
                      ].join(' ')}
                    >
                      <Upload size={17} />
                    </span>
                    <p className="text-[14px] font-medium text-gray-700 dark:text-gray-300">
                      {isDragOver ? 'Drop it here' : 'Drag & drop your SBOM file'}
                    </p>
                    <p className="text-[12px] text-gray-400 dark:text-gray-500 mt-1">
                      or{' '}
                      <span className="text-[#bf0000] dark:text-red-400 underline underline-offset-2 decoration-dotted">
                        browse files
                      </span>{' '}
                      &mdash; .json only
                    </p>
                  </div>)
                )}

                <ErrorText message={errors.file_error} />
              </section>
            </div>

            {/* Footer */}
            <div className="px-7 py-4 border-t border-gray-100 dark:border-white/[0.07] flex items-center justify-between gap-4">
              <p className="text-[12px] text-gray-400 dark:text-gray-500">
                All fields are required to start a scan.
              </p>

              <button
                type="submit"
                disabled={isSubmitting || submitted}
                className={[
                  'inline-flex items-center gap-2 px-5 h-10 rounded-lg text-[13px] font-semibold transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#bf0000]',
                  submitted
                    ? 'bg-emerald-600 text-white cursor-default'
                    : isSubmitting
                    ? 'bg-[#bf0000]/70 text-white cursor-wait'
                    : 'bg-[#bf0000] hover:bg-[#a00000] active:scale-[0.98] text-white shadow-sm shadow-red-900/20',
                ].join(' ')}
              >
                {submitted ? (
                  <>
                    <CheckCircle2 size={15} />
                    Scan started
                  </>
                ) : isSubmitting ? (
                  <>
                    <svg
                      className="animate-spin"
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                    >
                      <circle
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeDasharray="40"
                        strokeDashoffset="15"
                        strokeLinecap="round"
                      />
                    </svg>
                    Starting…
                  </>
                ) : (
                  <>
                    <Play size={14} fill="currentColor" />
                    Start scan
                  </>
                )}
              </button>
            </div>
          </form>
        </Card>

        {/* Footer note */}
        <p className="text-center text-[12px] text-gray-400 dark:text-gray-600 mt-5">
          Scans are processed securely and results appear on your project dashboard.
        </p>
      </div>
    </div>
  )
}

export default RouteComponent;