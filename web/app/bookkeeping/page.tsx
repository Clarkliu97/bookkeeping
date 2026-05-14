import { OperatorClient } from "../operator-workspace-client";


export const dynamic = "force-dynamic";


export default function BookkeepingPage() {
  return <OperatorClient activeSection="bookkeeping" />;
}