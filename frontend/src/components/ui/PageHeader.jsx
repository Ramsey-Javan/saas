export default function PageHeader({ title, description, action }) {
  return (
    <div className="mb-6">
      <h1 className="text-xl font-bold text-gray-900">{title}</h1>
      {description && <p className="mt-1 text-sm text-gray-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}