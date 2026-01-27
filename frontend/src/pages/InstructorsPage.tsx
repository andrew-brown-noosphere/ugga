import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, User, Star, Mail, ChevronRight, ChevronLeft, Building2 } from 'lucide-react'
import { getProfessors } from '../lib/api'

const PAGE_SIZE = 25

// Departments with claimed faculty profiles (verified instructors)
// Note: All instructors are searchable, but filter by department only works for claimed profiles
const DEPARTMENTS = [
  { code: '', label: 'All Instructors' },
  { code: 'MATH', label: 'Mathematics' },
  { code: 'CHEM', label: 'Chemistry' },
  { code: 'ENGL', label: 'English' },
  { code: 'CSCI', label: 'Computer Science' },
  { code: 'PSYC', label: 'Psychology' },
  { code: 'STAT', label: 'Statistics' },
  { code: 'SOCI', label: 'Sociology' },
  { code: 'HIST', label: 'History' },
  { code: 'CMLT', label: 'Comparative Literature' },
  { code: 'PHIL', label: 'Philosophy' },
  { code: 'PHYS', label: 'Physics' },
]

export default function InstructorsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialSearch = searchParams.get('search') || ''
  const initialDept = searchParams.get('dept') || ''
  const [search, setSearch] = useState(initialSearch)
  const [searchTerm, setSearchTerm] = useState(initialSearch)
  const [department, setDepartment] = useState(initialDept)
  const [page, setPage] = useState(0)

  // Update filters when URL changes
  useEffect(() => {
    const urlSearch = searchParams.get('search') || ''
    const urlDept = searchParams.get('dept') || ''
    if (urlSearch !== searchTerm || urlDept !== department) {
      setSearch(urlSearch)
      setSearchTerm(urlSearch)
      setDepartment(urlDept)
      setPage(0)
    }
  }, [searchParams])

  const { data: professors, isLoading } = useQuery({
    queryKey: ['professors', searchTerm, department, page],
    queryFn: () => getProfessors({
      search: searchTerm || undefined,
      department: department || undefined,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE
    }),
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearchTerm(search)
    setPage(0)
    // Update URL with params
    const params: Record<string, string> = {}
    if (search) params.search = search
    if (department) params.dept = department
    setSearchParams(params)
  }

  const handleDepartmentChange = (dept: string) => {
    setDepartment(dept)
    setPage(0)
    // Update URL
    const params: Record<string, string> = {}
    if (searchTerm) params.search = searchTerm
    if (dept) params.dept = dept
    setSearchParams(params)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Faculty Directory</h1>
        <p className="text-gray-600">Search all UGA instructors - browse profiles or help instructors claim their page</p>
      </div>

      {/* Search & Filter */}
      <div className="card">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search by name..."
              className="input pl-10"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="relative sm:w-48">
            <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <select
              className="input pl-10 appearance-none"
              value={department}
              onChange={(e) => handleDepartmentChange(e.target.value)}
            >
              {DEPARTMENTS.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn btn-primary">
            Search
          </button>
        </form>
      </div>

      {/* Results */}
      <div className="space-y-3">
        {isLoading ? (
          [...Array(5)].map((_, i) => (
            <div key={i} className="card animate-pulse">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 bg-gray-200 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <div className="h-5 bg-gray-200 rounded w-1/3" />
                  <div className="h-4 bg-gray-200 rounded w-1/4" />
                </div>
              </div>
            </div>
          ))
        ) : professors?.length === 0 ? (
          <div className="card text-center py-12">
            <p className="text-gray-500">
              {searchTerm
                ? 'No instructors found matching your search'
                : 'No instructors found'}
            </p>
          </div>
        ) : (
          <>
          {professors?.map((prof) => {
            const isUnclaimed = prof.id < 0
            return (
              <Link
                key={prof.id}
                to={`/instructors/${prof.id}`}
                className="card flex items-center gap-4 hover:shadow-md transition-shadow"
              >
                {/* Photo */}
                {prof.photo_url ? (
                  <img
                    src={prof.photo_url}
                    alt={prof.name}
                    className="w-16 h-16 rounded-lg object-cover"
                  />
                ) : (
                  <div className={`w-16 h-16 rounded-lg flex items-center justify-center ${isUnclaimed ? 'bg-gray-50 border-2 border-dashed border-gray-200' : 'bg-gray-100'}`}>
                    <User className="h-8 w-8 text-gray-300" />
                  </div>
                )}

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-gray-900">{prof.name}</h3>
                    {isUnclaimed && (
                      <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full">
                        Claim
                      </span>
                    )}
                  </div>
                  {prof.title && (
                    <p className="text-sm text-gray-600 truncate">{prof.title}</p>
                  )}
                  {prof.department_name && (
                    <p className="text-sm text-gray-500">{prof.department_name}</p>
                  )}
                  {prof.email && (
                    <p className="text-sm text-gray-500 flex items-center gap-1 mt-1">
                      <Mail className="h-3 w-3" />
                      {prof.email}
                    </p>
                  )}
                  {isUnclaimed && !prof.title && !prof.department_name && (
                    <p className="text-xs text-gray-400 mt-1">Profile can be claimed by this instructor</p>
                  )}
                </div>

                {/* Rating */}
                {prof.rmp_rating && (
                  <div className="text-center">
                    <div className="flex items-center gap-1 text-sm font-semibold">
                      <Star className="h-4 w-4 text-yellow-400 fill-yellow-400" />
                      <span>{prof.rmp_rating.toFixed(1)}</span>
                    </div>
                    <p className="text-xs text-gray-500">RMP</p>
                  </div>
                )}

                <ChevronRight className="h-5 w-5 text-gray-400" />
              </Link>
            )
          })}

          {/* Pagination */}
          <div className="flex items-center justify-between pt-4">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="btn btn-secondary flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </button>
            <span className="text-sm text-gray-500">
              Page {page + 1}
            </span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={professors && professors.length < PAGE_SIZE}
              className="btn btn-secondary flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
          </>
        )}
      </div>
    </div>
  )
}
