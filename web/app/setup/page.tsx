import { OperatorClient } from "../operator-workspace-client";


export const dynamic = "force-dynamic";


export default function SetupPage() {
  return <OperatorClient activeSection="setup" />;
}