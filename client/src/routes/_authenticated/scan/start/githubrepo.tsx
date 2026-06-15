import { Card } from '@/components/atomic/card';
import { Input } from '@/components/atomic/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  SelectCards,
} from '@/components/atomic/select';
import type { SelectCardOption } from '@/components/atomic/select';
import { useProjectNames } from '@/hooks/use-project';
import { useCreateGithubScan } from '@/hooks/use-scans';
import { useTrialStatus, isTrialExhausted } from '@/hooks/use-trial';
import type { CreateGithubScans } from '@/types/scan';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import {
  AlertCircle,
  CheckCircle2,
  Play,
} from 'lucide-react';
import React, { useState } from 'react';

export const Route = createFileRoute('/_authenticated/scan/start/githubrepo')({
  component: RouteComponent,
});

const SCAN_TYPES: SelectCardOption[] = [
  {
    value: 'sca',
    label: 'Code Scan',
    description: 'Analyse source code for vulnerabilities',
  },
  {
    value: 'sbom',
    label: 'SBOM Scan',
    description: 'Inspect software bill of materials',
  },
];

type FormErrors = Partial<CreateGithubScans>;

function StepBadge({ step }: { step: number }) {
  return (
    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[11px] font-medium bg-gray-100 dark:bg-white/10 text-gray-500 border border-gray-200 dark:border-white/10">
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
    <label className="block text-[11px] font-semibold uppercase tracking-widest text-gray-400 mb-1.5">
      {children}
    </label>
  );
}

function ErrorText({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p className="flex items-center gap-1.5 text-[12px] text-red-600 mt-1.5">
      <AlertCircle size={12} />
      {message}
    </p>
  );
}

function RouteComponent() {
  const navigate = useNavigate();
  const createScanMutation = useCreateGithubScan();

  // Trial mode (driven by the backend): hide SBOM and cap scans.
  const { data: trial } = useTrialStatus();
  const scanTypes = trial?.trial_mode ? SCAN_TYPES.filter(t => t.value !== 'sbom') : SCAN_TYPES;
  const trialBlocked = isTrialExhausted(trial);

  const [formData, setFormData] = useState<CreateGithubScans>({
    scan_name: '',
    project_id: '',
    scan_type: '',
    git_token: '',
    git_repo: '',
    git_rowner: '',
  });

  const { data: projects = [] } = useProjectNames();
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const clearError = (key: keyof CreateGithubScans) =>
    setErrors(prev => ({ ...prev, [key]: undefined }));

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    clearError(name as keyof CreateGithubScans);
  };

  const handleProjectChange = (value: string) => {
    setFormData(prev => ({ ...prev, project_id: value }));
    clearError('project_id');
  };

  const handleScanTypeChange = (value: string) => {
    setFormData(prev => ({ ...prev, scan_type: value }));
    clearError('scan_type');
  };

  const validateForm = () => {
    const newErrors: FormErrors = {};

    if (!formData.project_id) newErrors.project_id = 'Select project';
    if (!formData.scan_name) newErrors.scan_name = 'Scan name required';
    if (!formData.scan_type) newErrors.scan_type = 'Select scan type';
    if (!formData.git_token) newErrors.git_token = 'Token required';
    if (!formData.git_repo) newErrors.git_repo = 'Repository required';
    if (!formData.git_rowner) newErrors.git_rowner = 'Owner required';

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsSubmitting(true);

    try {
      await createScanMutation.mutateAsync(formData);

      setSubmitted(true);

      setTimeout(() => {
        navigate({
          from: '/scan/start',
          to: `../../project/${formData.project_id}`,
        });
      }, 800);
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-8xl mx-auto">
        <Card className="border shadow-sm rounded-xl overflow-hidden">
          
          {/* Header */}
          <div className="px-6">
            <h1 className="text-[22px] font-semibold">
              Start GitHub Scan
            </h1>
            <p className="text-[14px] mt-1">
              Connect your repository and start scanning.
            </p>
          </div>

          <div className="h-[3px] w-full bg-gradient-to-r from-[#bf0000] via-[#e03030] to-[#ff6060]" />

          <form onSubmit={handleSubmit}>
            <div className="px-7 py-6 space-y-7">

              {/* Section 1 */}
              <section>
                <SectionHeading step={1} title="Project & scan identity" />

                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <FieldLabel>Project</FieldLabel>
                    <Select value={formData.project_id} onValueChange={handleProjectChange}>
                      <SelectTrigger className={errors.project_id ? 'border-red-500' : ''}>
                        <SelectValue placeholder="Select project" />
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

                  <div>
                    <FieldLabel>Scan Name</FieldLabel>
                    <Input
                      name="scan_name"
                      value={formData.scan_name}
                      onChange={handleInputChange}
                      className={errors.scan_name ? 'border-red-500' : ''}
                    />
                    <ErrorText message={errors.scan_name} />
                  </div>
                </div>
              </section>

              <hr className="border-gray-100" />

              {/* Section 2 */}
              <section>
                <SectionHeading step={2} title="Scan type" />
                <SelectCards
                  options={scanTypes}
                  value={formData.scan_type}
                  onValueChange={handleScanTypeChange}
                />
                <ErrorText message={errors.scan_type} />
              </section>

              <hr className="border-gray-100" />

              {/* Section 3 */}
              <section>
                <SectionHeading step={3} title="GitHub configuration" />

                <div className="grid sm:grid-cols-2 gap-4">

                  <div>
                    <FieldLabel>GitHub Token</FieldLabel>
                    <Input
                      name="git_token"
                      value={formData.git_token}
                      onChange={handleInputChange}
                    />
                    <ErrorText message={errors.git_token} />
                  </div>

                  <div>
                    <FieldLabel>Repository Owner</FieldLabel>
                    <Input
                      name="git_rowner"
                      value={formData.git_rowner}
                      onChange={handleInputChange}
                    />
                    <ErrorText message={errors.git_rowner} />
                  </div>

                  <div>
                    <FieldLabel>Repository Name</FieldLabel>
                    <Input
                      name="git_repo"
                      value={formData.git_repo}
                      onChange={handleInputChange}
                    />
                    <ErrorText message={errors.git_repo} />
                  </div>

                </div>
              </section>
            </div>

            {/* Footer */}
            <div className="px-7 py-4 border-t flex justify-between items-center">
              <div className="text-[12px] text-gray-400">
                {trial?.trial_mode ? (
                  <span className={trialBlocked ? 'text-red-600 dark:text-red-400 font-medium' : ''}>
                    Trial: {trial.used}/{trial.limit} scans used
                    {trialBlocked
                      ? ' — limit reached. Contact us to upgrade.'
                      : ` (${trial.remaining} left)`}
                  </span>
                ) : (
                  'All fields are required.'
                )}
              </div>

              <button
                type="submit"
                disabled={isSubmitting || submitted || trialBlocked}
                className={[
                  'inline-flex items-center gap-2 px-5 h-10 rounded-lg text-[13px] font-semibold',
                  trialBlocked
                    ? 'bg-gray-400 dark:bg-[#505050] text-white cursor-not-allowed'
                    : submitted
                    ? 'bg-emerald-600 text-white'
                    : isSubmitting
                    ? 'bg-[#bf0000]/70 text-white'
                    : 'bg-[#bf0000] hover:bg-[#a00000] text-white',
                ].join(' ')}
              >
                {submitted ? (
                  <>
                    <CheckCircle2 size={15} />
                    Scan started
                  </>
                ) : isSubmitting ? (
                  'Starting...'
                ) : (
                  <>
                    <Play size={14} />
                    Start scan
                  </>
                )}
              </button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}