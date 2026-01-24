import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, GraduationCap, ChevronRight, BookOpen, AlertTriangle } from 'lucide-react'
import { clsx } from 'clsx'
import { getPrograms } from '../lib/api'
import type { Program } from '../types'

const COLLEGE_NAMES: Record<string, string> = {
  ARTS: 'Franklin College of Arts & Sciences',
  BUS: 'Terry College of Business',
  ENG: 'College of Engineering',
  AGRI: 'College of Agricultural & Environmental Sciences',
  EDU: 'College of Education',
  FAM: 'College of Family & Consumer Sciences',
  FOR: 'Warnell School of Forestry',
  JOUR: 'Grady College of Journalism',
  LAW: 'School of Law',
  PHAR: 'College of Pharmacy',
  PUB: 'School of Public & International Affairs',
  SOC: 'School of Social Work',
  VET: 'College of Veterinary Medicine',
  ECOL: 'Odum School of Ecology',
  PH: 'College of Public Health',
}

const degreeTypes = [
  { value: '', label: 'All Types' },
  { value: 'BS', label: 'Bachelor of Science' },
  { value: 'BA', label: 'Bachelor of Arts' },
  { value: 'AB', label: 'Bachelor of Arts (AB)' },
  { value: 'BBA', label: 'Bachelor of Business' },
  { value: 'MINOR', label: 'Minor' },
  { value: 'MS', label: 'Master of Science' },
  { value: 'PHD', label: 'Doctorate' },
]

export default function ProgramsPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [degreeFilter, setDegreeFilter] = useState('')
  const [selectedProgram, setSelectedProgram] = useState<Program | null>(null)

  const { data: programs, isLoading } = useQuery({
    queryKey: ['programs'],
    queryFn: () => getPrograms(),
  })

  // Filter programs
  const filteredPrograms = (programs || []).filter((program) => {
    const matchesSearch =
      program.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      program.department?.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesDegree = !degreeFilter || program.degree_type === degreeFilter
    return matchesSearch && matchesDegree
  })

  // Group by degree type
  const groupedPrograms = filteredPrograms.reduce((acc, program) => {
    const type = program.degree_type
    if (!acc[type]) acc[type] = []
    acc[type].push(program)
    return acc
  }, {} as Record<string, Program[]>)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Academic Programs</h1>
        <p className="text-gray-600">
          Explore majors, minors, and graduate programs at UGA
        </p>
      </div>

      {/* Search and Filters */}
      <div className="card">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search programs..."
              className="input pl-10"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <select
            className="input md:w-64"
            value={degreeFilter}
            onChange={(e) => setDegreeFilter(e.target.value)}
          >
            {degreeTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Results */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Program list */}
        <div className="space-y-6">
          {isLoading ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="card animate-pulse">
                  <div className="h-5 bg-gray-200 rounded w-1/2 mb-2" />
                  <div className="h-4 bg-gray-100 rounded w-1/3" />
                </div>
              ))}
            </div>
          ) : (
            Object.entries(groupedPrograms).map(([type, typePrograms]) => (
              <div key={type}>
                <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
                  <GraduationCap className="h-5 w-5 mr-2 text-brand-600" />
                  {degreeTypes.find((d) => d.value === type)?.label || type}
                  <span className="ml-2 text-sm font-normal text-gray-500">
                    ({typePrograms.length})
                  </span>
                </h2>
                <div className="space-y-2">
                  {typePrograms.map((program) => (
                    <button
                      key={program.id}
                      onClick={() => setSelectedProgram(program)}
                      className={clsx(
                        'w-full card hover:shadow-md transition-shadow text-left flex items-center justify-between',
                        selectedProgram?.id === program.id && 'ring-2 ring-brand-600'
                      )}
                    >
                      <div>
                        <h3 className="font-medium text-gray-900">
                          {program.name}
                        </h3>
                        {program.department && program.department !== program.name && (
                          <p className="text-sm text-gray-500">
                            {program.department}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="badge badge-info">{program.degree_type}</span>
                        <ChevronRight className="h-5 w-5 text-gray-400" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ))
          )}

          {!isLoading && filteredPrograms.length === 0 && (
            <div className="card text-center py-8">
              <p className="text-gray-500">No programs found</p>
            </div>
          )}
        </div>

        {/* Program details */}
        <div className="md:sticky md:top-4 h-fit">
          {selectedProgram ? (
            <ProgramDetails program={selectedProgram} />
          ) : (
            <div className="card text-center py-12">
              <GraduationCap className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">
                Select a program to view details
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ProgramDetails({ program }: { program: Program }) {
  const collegeName = COLLEGE_NAMES[program.college_code] || program.college_code
  const totalCourses = program.requirements?.reduce((sum, r) => sum + (r.courses?.length || 0), 0) || 0

  return (
    <div className="card">
      <div className="flex items-start justify-between mb-4">
        <div>
          <span className="badge badge-info mb-2">{program.degree_type}</span>
          <h2 className="text-xl font-bold text-gray-900">{program.name}</h2>
          {program.department && program.department !== program.name && (
            <p className="text-gray-500">{program.department}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 py-4 border-y">
        <div>
          <p className="text-sm text-gray-500">Total Hours</p>
          <p className="text-lg font-semibold">{program.total_hours || '~120'}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">College</p>
          <p className="text-sm font-semibold">{collegeName}</p>
        </div>
      </div>

      {program.overview && (
        <p className="text-sm text-gray-600 mt-4">{program.overview}</p>
      )}

      <div className="mt-4 space-y-3">
        <h3 className="font-medium text-gray-900">Requirements</h3>

        {program.requirements && program.requirements.length > 0 ? (
          <div className="space-y-2">
            {program.requirements.map((req) => (
              <div key={req.id} className="p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">{req.name}</span>
                  {req.required_hours && (
                    <span className="text-xs text-gray-500">{req.required_hours} hrs</span>
                  )}
                </div>
                {req.courses && req.courses.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {req.courses.slice(0, 5).map((course, i) => (
                      <span key={`${course.course_code}-${i}`} className="text-xs px-2 py-0.5 bg-white rounded text-gray-600 font-mono">
                        {course.course_code}
                      </span>
                    ))}
                    {req.courses.length > 5 && (
                      <span className="text-xs text-gray-400">+{req.courses.length - 5} more</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-amber-800">
                Detailed requirements not yet available. Check the official UGA Bulletin for complete information.
              </p>
            </div>
          </div>
        )}

        <div className="pt-4 space-y-2">
          {program.bulletin_url && (
            <a
              href={program.bulletin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-outline w-full flex items-center justify-center"
            >
              <BookOpen className="h-4 w-4 mr-2" />
              View in Official Bulletin
            </a>
          )}
        </div>

        {totalCourses < 5 && (
          <p className="text-xs text-gray-400 text-center">
            Data sourced from public UGA schedules. Always verify with your advisor.
          </p>
        )}
      </div>
    </div>
  )
}
