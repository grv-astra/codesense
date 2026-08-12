//edit

// src/routes/_authenticated/project/$projectId/edit.tsx

import React, { useState, useEffect } from 'react';
import { createFileRoute, useNavigate, useParams } from '@tanstack/react-router';
import { Input } from '@/components/atomic/input';
import type { CreateProjectDetails } from '@/types/project';
import { useProjectDetails, useUpdateProject } from '@/hooks/use-project';
import { Card } from '@/components/atomic/card';
import { DotsLoader } from '@/components/atomic/loader';
import { AlertCircle, CheckCircle2, Info, Save } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/atomic/tooltip';

export const Route = createFileRoute('/_authenticated/project/$projectId/edit')({
  component: RouteComponent,
});

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
      <span className="text-[13px] font-medium text-gray-700 dark:text-gray-300">{title}</span>
      <div className="flex-1 border-t border-gray-100 dark:border-white/10" />
    </div>
  );
}

function FieldLabel({ children, tooltip }: { children: React.ReactNode; tooltip?: string }) {
  return (
    <div className="flex items-center gap-1.5 mb-1.5">
      <label className="block text-[11px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500">
        {children}
      </label>
      {tooltip && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Info className="w-3 h-3 text-gray-400 dark:text-gray-500 cursor-pointer" />
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{tooltip}</p>
          </TooltipContent>
        </Tooltip>
      )}
    </div>
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

function RouteComponent() {
  const navigate = useNavigate();
  const { projectId } = useParams({ from: '/_authenticated/project/$projectId/edit' });
  const updateProjectMutation = useUpdateProject();
  const { data: project, isLoading, error } = useProjectDetails(projectId);

  const [formData, setFormData] = useState<CreateProjectDetails>({
    name: '',
    preset: '',
    description: ''
  });

  const [errors, setErrors] = useState<Partial<CreateProjectDetails>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  // Populate form with existing project data
  useEffect(() => {
    if (project) {
      setFormData({
        name: project.name || '',
        preset: project.preset || '',
        description: project.description || ''
      });
    }
  }, [project]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    if (errors[name as keyof CreateProjectDetails]) {
      setErrors(prev => ({
        ...prev,
        [name]: undefined
      }));
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Partial<CreateProjectDetails> = {};
    if (!formData.name.trim()) newErrors.name = 'Project name is required';
    if (!formData.preset) newErrors.preset = 'Please select a preset';
    if (!formData.description.trim()) newErrors.description = 'Description is required';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) return;
    setIsSubmitting(true);
    try {
      const projectData = {
        name: formData.name,
        preset: formData.preset,
        description: formData.description
      };

      await updateProjectMutation.mutateAsync({ projectId, projectData });
      setSubmitted(true);
      setTimeout(() => {
        navigate({ to: '/project/$projectId/settings', params: { projectId } });
      }, 800);
    } catch (error) {
      console.error('Error updating project:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    navigate({ to: '/project/$projectId/settings', params: { projectId } });
  };

  if (isLoading) {
    return (
      <div className="p-6 max-w-8xl mx-auto">
        <DotsLoader />
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <Card className="border shadow-sm rounded-xl overflow-hidden">
          <div className="px-6 pt-6">
            <h1 className="text-[22px] font-semibold text-red-600 leading-tight">Error</h1>
          </div>
          <div className="p-6">
            <p className="text-gray-600 mb-4">
              {error ? 'Failed to load project details.' : 'Project not found.'}
            </p>
            <button
              onClick={() => navigate({ to: '/project/list' })}
              className="bg-gray-500 hover:bg-gray-600 text-white font-semibold py-2 px-4 rounded"
            >
              Back to Projects
            </button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="min-h-screen p-8">
        <div className="max-w-8xl mx-auto">
          <Card className="border shadow-sm rounded-xl overflow-hidden">
            {/* Page heading */}
            <div className="px-6">
              <div className="flex items-center gap-2 text-[12px] mb-3 font-medium uppercase tracking-widest">
                <span>Projects</span>
                <span>/</span>
                <span>{project.name}</span>
                <span>/</span>
                <span>Edit</span>
              </div>
              <h1 className="text-[22px] font-semibold text-gray-900 dark:text-white leading-tight">
                Edit project
              </h1>
              <p className="text-[14px] mt-1">
                Update the name, preset, or description for this project.
              </p>
            </div>

            {/* Card top accent bar */}
            <div className="h-[3px] w-full bg-gradient-to-r from-[#bf0000] via-[#e03030] to-[#ff6060]" />

            <form onSubmit={handleSubmit} noValidate>
              <div className="px-7 py-6 space-y-7">
                <section>
                  <SectionHeading step={1} title="Project details" />

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <FieldLabel tooltip="Enter a unique name to identify your project.">
                        Project name
                      </FieldLabel>
                      <Input
                        name="name"
                        value={formData.name}
                        onChange={handleInputChange}
                        placeholder="Enter project name"
                        className={[
                          'h-10 text-[14px]',
                          errors.name ? 'border-red-500 dark:border-red-500 bg-red-50 dark:bg-red-900/10' : '',
                        ].join(' ')}
                      />
                      <ErrorText message={errors.name} />
                    </div>

                    <div>
                      <FieldLabel tooltip="Enter a preset (type of project) template to configure default project settings.">
                        Preset
                      </FieldLabel>
                      <Input
                        name="preset"
                        value={formData.preset}
                        onChange={handleInputChange}
                        placeholder="Enter preset"
                        className={[
                          'h-10 text-[14px]',
                          errors.preset ? 'border-red-500 dark:border-red-500 bg-red-50 dark:bg-red-900/10' : '',
                        ].join(' ')}
                      />
                      <ErrorText message={errors.preset} />
                    </div>
                  </div>

                  <div className="mt-4">
                    <FieldLabel tooltip="Briefly describe the purpose or scope of this project.">
                      Description
                    </FieldLabel>
                    <Input
                      name="description"
                      value={formData.description}
                      onChange={handleInputChange}
                      placeholder="Enter project description"
                      className={[
                        'h-10 text-[14px]',
                        errors.description ? 'border-red-500 dark:border-red-500 bg-red-50 dark:bg-red-900/10' : '',
                      ].join(' ')}
                    />
                    <ErrorText message={errors.description} />
                  </div>
                </section>
              </div>

              {/* Footer */}
              <div className="px-7 py-4 border-t border-gray-100 dark:border-white/[0.07] flex items-center justify-between gap-4">
                <button
                  type="button"
                  onClick={handleCancel}
                  className="px-5 h-10 rounded-lg text-[13px] font-semibold border border-gray-200 dark:border-white/10 hover:bg-gray-50 dark:hover:bg-white/[0.04] transition-colors"
                >
                  Cancel
                </button>

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
                      Saved
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
                      Saving…
                    </>
                  ) : (
                    <>
                      <Save size={14} />
                      Save changes
                    </>
                  )}
                </button>
              </div>
            </form>
          </Card>
        </div>
      </div>
    </TooltipProvider>
  );
}
