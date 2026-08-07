import JobCard from './JobCard.jsx'

export default function JobGrid({ jobs }) {
  return (
    <div className="job-grid">
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} />
      ))}
    </div>
  )
}
