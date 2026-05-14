import { OperatorClient } from "../operator-workspace-client";


export const dynamic = "force-dynamic";


export default function ReportsPage() {
  return <OperatorClient activeSection="reports" />;
}