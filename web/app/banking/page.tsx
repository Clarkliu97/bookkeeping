import { OperatorClient } from "../operator-workspace-client";


export const dynamic = "force-dynamic";


export default function BankingPage() {
  return <OperatorClient activeSection="banking" />;
}