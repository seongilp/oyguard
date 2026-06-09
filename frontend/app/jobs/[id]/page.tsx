import { JobDetail } from "@/components/job-detail";

interface JobPageProps {
  params: Promise<{ id: string }>;
}

export default async function JobPage({ params }: JobPageProps) {
  const { id } = await params;
  return <JobDetail id={id} />;
}
