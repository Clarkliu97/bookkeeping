import { OperatorClient } from "./operator-workspace-client";


export const dynamic = "force-dynamic";


export default function HomePage() {
  return <OperatorClient activeSection="dashboard" />;
}
