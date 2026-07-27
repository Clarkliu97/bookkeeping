import { OperatorClient } from "../operator-workspace-client";


export const dynamic = "force-dynamic";


export default function BudgetForecastPage() {
  return <OperatorClient activeSection="budget_forecast" />;
}
