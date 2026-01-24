import { useState, useEffect } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Plus, Trash2, Loader2, BookOpen, GraduationCap } from 'lucide-react'
import { clsx } from 'clsx'
import { addCompletedCoursesBulk, setAuthToken } from '../lib/api'
import type { CompletedCourseCreate } from '../types'
import { GRADE_OPTIONS } from '../types'

interface CourseEntryModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

interface CourseEntry {
  id: string
  course_code: string
  grade: string  // Empty string means no grade (for privacy)
  credit_hours: number
  semester: string
  year: number | null
}

const SEMESTER_OPTIONS = ['Fall', 'Spring', 'Summer', 'Maymester']
const CURRENT_YEAR = new Date().getFullYear()
const YEAR_OPTIONS = Array.from({ length: 10 }, (_, i) => CURRENT_YEAR - i)

function createEmptyEntry(): CourseEntry {
  return {
    id: crypto.randomUUID(),
    course_code: '',
    grade: '',  // Default to no grade for privacy
    credit_hours: 3,
    semester: 'Fall',
    year: CURRENT_YEAR,
  }
}

export default function CourseEntryModal({ isOpen, onClose, onSuccess }: CourseEntryModalProps) {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()
  const [entries, setEntries] = useState<CourseEntry[]>([createEmptyEntry()])
  const [error, setError] = useState<string | null>(null)

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setEntries([createEmptyEntry()])
      setError(null)
    }
  }, [isOpen])

  const saveMutation = useMutation({
    mutationFn: async (courses: CompletedCourseCreate[]) => {
      const token = await getToken()
      setAuthToken(token)
      return addCompletedCoursesBulk(courses)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['completedCourses'] })
      queryClient.invalidateQueries({ queryKey: ['transcriptSummary'] })
      queryClient.invalidateQueries({ queryKey: ['degreeAudit'] })
      queryClient.invalidateQueries({ queryKey: ['quickProgress'] })
      onSuccess?.()
      onClose()
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to save courses')
    },
  })

  const handleAddEntry = () => {
    setEntries([...entries, createEmptyEntry()])
  }

  const handleRemoveEntry = (id: string) => {
    if (entries.length > 1) {
      setEntries(entries.filter((e) => e.id !== id))
    }
  }

  const handleUpdateEntry = (id: string, field: keyof CourseEntry, value: string | number | null) => {
    setEntries(
      entries.map((e) => (e.id === id ? { ...e, [field]: value } : e))
    )
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Validate entries
    const validEntries = entries.filter((e) => e.course_code.trim())
    if (validEntries.length === 0) {
      setError('Please enter at least one course')
      return
    }

    // Check for valid course codes (basic format check)
    const courseCodeRegex = /^[A-Z]{2,4}\s*\d{4}[A-Z]?$/i
    for (const entry of validEntries) {
      if (!courseCodeRegex.test(entry.course_code.trim())) {
        setError(`Invalid course code format: ${entry.course_code}. Use format like "CSCI 1301"`)
        return
      }
    }

    // Convert to API format
    const courses: CompletedCourseCreate[] = validEntries.map((e) => ({
      course_code: e.course_code.toUpperCase().trim(),
      grade: e.grade || undefined,  // Omit if empty (privacy)
      credit_hours: e.credit_hours,
      semester: e.year ? `${e.semester} ${e.year}` : undefined,
      year: e.year || undefined,
    }))

    saveMutation.mutate(courses)
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-br from-brand-600 to-brand-700 px-6 py-5 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-white/20 rounded-lg">
                <GraduationCap className="h-6 w-6" />
              </div>
              <div>
                <h2 className="text-xl font-bold">Add Completed Courses</h2>
                <p className="text-white/80 text-sm">Enter courses you've already completed</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-full hover:bg-white/20 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <p className="text-white/60 text-xs mt-3">
            Grades are optional. We never share grade or GPA information with third parties.
          </p>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-auto p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          <div className="space-y-4">
            {entries.map((entry, index) => (
              <div
                key={entry.id}
                className="p-4 bg-gray-50 rounded-xl border border-gray-200"
              >
                <div className="flex items-start justify-between mb-3">
                  <span className="text-sm font-medium text-gray-500">
                    Course {index + 1}
                  </span>
                  {entries.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveEntry(entry.id)}
                      className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* Course Code */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Course Code
                    </label>
                    <div className="relative">
                      <BookOpen className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                      <input
                        type="text"
                        value={entry.course_code}
                        onChange={(e) =>
                          handleUpdateEntry(entry.id, 'course_code', e.target.value)
                        }
                        placeholder="CSCI 1301"
                        className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                      />
                    </div>
                  </div>

                  {/* Grade */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Grade (optional)
                    </label>
                    <select
                      value={entry.grade}
                      onChange={(e) =>
                        handleUpdateEntry(entry.id, 'grade', e.target.value)
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                    >
                      <option value="">Prefer not to say</option>
                      {GRADE_OPTIONS.map((grade) => (
                        <option key={grade} value={grade}>
                          {grade}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Credit Hours */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Credit Hours
                    </label>
                    <select
                      value={entry.credit_hours}
                      onChange={(e) =>
                        handleUpdateEntry(entry.id, 'credit_hours', parseInt(e.target.value))
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                    >
                      {[1, 2, 3, 4, 5, 6].map((hours) => (
                        <option key={hours} value={hours}>
                          {hours} {hours === 1 ? 'hour' : 'hours'}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Semester & Year */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Semester (optional)
                    </label>
                    <div className="flex gap-2">
                      <select
                        value={entry.semester}
                        onChange={(e) =>
                          handleUpdateEntry(entry.id, 'semester', e.target.value)
                        }
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                      >
                        {SEMESTER_OPTIONS.map((sem) => (
                          <option key={sem} value={sem}>
                            {sem}
                          </option>
                        ))}
                      </select>
                      <select
                        value={entry.year || ''}
                        onChange={(e) =>
                          handleUpdateEntry(
                            entry.id,
                            'year',
                            e.target.value ? parseInt(e.target.value) : null
                          )
                        }
                        className="w-24 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                      >
                        <option value="">Year</option>
                        {YEAR_OPTIONS.map((year) => (
                          <option key={year} value={year}>
                            {year}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Add Another */}
          <button
            type="button"
            onClick={handleAddEntry}
            className="mt-4 w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-gray-300 rounded-xl text-gray-500 hover:border-brand-400 hover:text-brand-600 transition-colors"
          >
            <Plus className="h-5 w-5" />
            Add Another Course
          </button>
        </form>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-50 border-t flex items-center justify-between">
          <p className="text-xs text-gray-500">
            {entries.filter((e) => e.course_code.trim()).length} course(s) to add
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 hover:bg-gray-200 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={saveMutation.isPending}
              className={clsx(
                'px-6 py-2 bg-brand-600 text-white rounded-lg font-medium transition-colors',
                saveMutation.isPending
                  ? 'opacity-50 cursor-not-allowed'
                  : 'hover:bg-brand-700'
              )}
            >
              {saveMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
                  Saving...
                </>
              ) : (
                'Save Courses'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
