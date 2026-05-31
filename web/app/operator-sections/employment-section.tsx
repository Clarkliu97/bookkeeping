import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { EmptyState, Field, StatusPill } from "../operator-ui";
import { formatDate, formatDateTime, formatMoney, type OperatorState } from "../operator-state";


type EmploymentWorker = {
  id: string;
  worker_code: string;
  display_name: string;
  legal_name: string | null;
  worker_kind: string;
  date_of_birth: string | null;
  primary_email: string | null;
  primary_phone: string | null;
  address_summary: string | null;
  emergency_contact_summary: string | null;
  privacy_note: string | null;
  is_active: boolean;
  note: string | null;
};

type EmploymentEngagement = {
  id: string;
  worker_id: string;
  engagement_type: string;
  employment_basis: string;
  start_date: string;
  expected_end_date: string | null;
  actual_end_date: string | null;
  department: string | null;
  role_name: string;
  manager_name: string | null;
  primary_work_location: string | null;
  pay_cycle_reference: string | null;
  status: string;
  status_reason: string | null;
  note: string | null;
};

type EmploymentWorkRights = {
  id: string;
  worker_id: string;
  engagement_id: string | null;
  work_rights_basis: string;
  review_status: string;
  visa_subclass: string | null;
  visa_label: string | null;
  visa_grant_date: string | null;
  visa_expiry_date: string | null;
  work_condition_summary: string | null;
  hours_restriction_summary: string | null;
  sponsorship_required: boolean;
  sponsoring_entity_note: string | null;
  vevo_checked_at: string | null;
  next_review_due_at: string | null;
  reviewer_user_id: string | null;
  review_note: string | null;
};

type EmploymentCompensation = {
  id: string;
  engagement_id: string;
  remuneration_basis: string;
  expected_base_amount: string | null;
  tax_profile: string | null;
  superannuation_category: string | null;
  workers_comp_category: string | null;
  payroll_tax_in_scope: boolean;
  leave_profile: string | null;
  reimbursement_allowed: boolean;
  asset_issue_allowed: boolean;
  expense_account_id: string | null;
  liability_account_id: string | null;
  tfn_declaration_received: boolean;
  super_choice_received: boolean;
  abn_provided: boolean;
  gst_registered_known: boolean;
  note: string | null;
};

type EmploymentLeaveSnapshot = {
  id: string;
  engagement_id: string;
  snapshot_date: string;
  annual_leave_hours: string;
  personal_leave_hours: string;
  long_service_leave_hours: string;
  leave_value_amount: string;
  current_lsl_value_amount: string;
  non_current_lsl_value_amount: string;
  note: string | null;
  reviewed_by_user_id: string | null;
};

type EmploymentReimbursement = {
  id: string;
  worker_id: string;
  engagement_id: string | null;
  reimbursement_date: string;
  description: string;
  amount: string;
  status: string;
  note: string | null;
};

type EmploymentIssuedAsset = {
  id: string;
  worker_id: string;
  engagement_id: string | null;
  asset_name: string;
  asset_type: string | null;
  serial_number: string | null;
  assigned_on: string;
  due_back_on: string | null;
  returned_on: string | null;
  status: string;
  note: string | null;
};

type EmploymentLinkedDocument = {
  link_id: string;
  document_id: string;
  original_filename: string;
  media_type: string | null;
  byte_size: number;
  note: string | null;
  linked_at: string;
};

type EmploymentQueueItem = {
  worker_id: string;
  worker_name: string;
  engagement_id: string | null;
  title: string;
  status: string;
  due_date: string | null;
  detail: string | null;
};

type EmploymentDashboard = {
  total_workers: number;
  active_engagements: number;
  onboarding_count: number;
  expiring_work_rights_count: number;
  missing_document_count: number;
  onboarding_items: EmploymentQueueItem[];
  work_rights_due_items: EmploymentQueueItem[];
  finalization_items: EmploymentQueueItem[];
};

type EmploymentWorkerDetail = EmploymentWorker & {
  engagements: EmploymentEngagement[];
  work_rights_records: EmploymentWorkRights[];
  compensation_profiles: EmploymentCompensation[];
  leave_snapshots: EmploymentLeaveSnapshot[];
  reimbursements: EmploymentReimbursement[];
  issued_assets: EmploymentIssuedAsset[];
  linked_documents: EmploymentLinkedDocument[];
};

type HeadcountReport = {
  total_workers: number;
  active_engagements: number;
  contractor_engagements: number;
  rows: Array<{
    worker_id: string;
    worker_name: string;
    worker_kind: string;
    engagement_id: string;
    engagement_type: string;
    status: string;
    department: string | null;
    role_name: string;
  }>;
};

type WorkRightsReport = {
  rows: Array<{
    worker_id: string;
    worker_name: string;
    engagement_id: string | null;
    review_status: string;
    work_rights_basis: string;
    visa_label: string | null;
    visa_expiry_date: string | null;
    next_review_due_at: string | null;
    restriction_summary: string | null;
  }>;
};

type LeaveLiabilityReport = {
  rows: Array<{
    worker_id: string;
    worker_name: string;
    engagement_id: string;
    engagement_status: string;
    snapshot_date: string;
    annual_leave_hours: string;
    long_service_leave_hours: string;
    leave_value_amount: string;
    current_lsl_value_amount: string;
    non_current_lsl_value_amount: string;
  }>;
};

type ContractorReviewReport = {
  rows: Array<{
    worker_id: string;
    worker_name: string;
    engagement_id: string;
    engagement_type: string;
    status: string;
    remuneration_basis: string | null;
    abn_provided: boolean | null;
    gst_registered_known: boolean | null;
    payroll_tax_in_scope: boolean | null;
    note: string | null;
  }>;
};

type WorkerDraft = {
  worker_code: string;
  display_name: string;
  legal_name: string;
  worker_kind: string;
  date_of_birth: string;
  primary_email: string;
  primary_phone: string;
  address_summary: string;
  emergency_contact_summary: string;
  privacy_note: string;
  is_active: boolean;
  note: string;
};

type EngagementDraft = {
  engagement_type: string;
  employment_basis: string;
  start_date: string;
  expected_end_date: string;
  actual_end_date: string;
  department: string;
  role_name: string;
  manager_name: string;
  primary_work_location: string;
  pay_cycle_reference: string;
  status: string;
  status_reason: string;
  note: string;
};

type WorkRightsDraft = {
  engagement_id: string;
  work_rights_basis: string;
  review_status: string;
  visa_subclass: string;
  visa_label: string;
  visa_grant_date: string;
  visa_expiry_date: string;
  work_condition_summary: string;
  hours_restriction_summary: string;
  sponsorship_required: boolean;
  sponsoring_entity_note: string;
  vevo_checked_at: string;
  next_review_due_at: string;
  reviewer_user_id: string;
  review_note: string;
};

type CompensationDraft = {
  remuneration_basis: string;
  expected_base_amount: string;
  tax_profile: string;
  superannuation_category: string;
  workers_comp_category: string;
  payroll_tax_in_scope: boolean;
  leave_profile: string;
  reimbursement_allowed: boolean;
  asset_issue_allowed: boolean;
  expense_account_id: string;
  liability_account_id: string;
  tfn_declaration_received: boolean;
  super_choice_received: boolean;
  abn_provided: boolean;
  gst_registered_known: boolean;
  note: string;
};

type LeaveSnapshotDraft = {
  snapshot_date: string;
  annual_leave_hours: string;
  personal_leave_hours: string;
  long_service_leave_hours: string;
  leave_value_amount: string;
  current_lsl_value_amount: string;
  non_current_lsl_value_amount: string;
  note: string;
  reviewed_by_user_id: string;
};

type ReimbursementDraft = {
  engagement_id: string;
  reimbursement_date: string;
  description: string;
  amount: string;
  status: string;
  note: string;
};

type IssuedAssetDraft = {
  engagement_id: string;
  asset_name: string;
  asset_type: string;
  serial_number: string;
  assigned_on: string;
  due_back_on: string;
  returned_on: string;
  status: string;
  note: string;
};

const WORKER_KIND_OPTIONS = ["individual", "entity"];
const ENGAGEMENT_TYPE_OPTIONS = ["employee", "director", "individual_contractor", "contractor_entity", "labour_hire", "intern"];
const EMPLOYMENT_STATUS_OPTIONS = ["draft", "onboarding", "active", "active_with_restrictions", "on_paid_leave", "on_unpaid_leave", "suspended", "on_notice", "ended", "archived"];
const WORK_RIGHTS_BASIS_OPTIONS = ["australian_citizen", "permanent_resident", "new_zealand_citizen", "employer_sponsored_temporary_visa", "other_temporary_visa", "student_visa", "working_holiday_visa", "bridging_visa", "unknown_review_required", "no_verified_work_right"];
const WORK_RIGHTS_STATUS_OPTIONS = ["not_required", "pending_evidence", "pending_review", "verified", "verified_with_restrictions", "expiring_soon", "expired", "blocked_pending_review"];
const REMUNERATION_BASIS_OPTIONS = ["salary", "hourly", "day_rate", "commission", "contractor_fee", "director_fee", "unpaid"];
const REIMBURSEMENT_STATUS_OPTIONS = ["draft", "submitted", "reviewed", "paid", "rejected"];
const ASSET_STATUS_OPTIONS = ["issued", "returned", "lost", "damaged"];


function todayIso() {
  return new Date().toISOString().slice(0, 10);
}


function emptyToNull(value: string) {
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}


function createEmptyWorkerDraft(): WorkerDraft {
  return {
    worker_code: "",
    display_name: "",
    legal_name: "",
    worker_kind: "individual",
    date_of_birth: "",
    primary_email: "",
    primary_phone: "",
    address_summary: "",
    emergency_contact_summary: "",
    privacy_note: "",
    is_active: true,
    note: "",
  };
}


function createEmptyEngagementDraft(): EngagementDraft {
  return {
    engagement_type: "employee",
    employment_basis: "",
    start_date: todayIso(),
    expected_end_date: "",
    actual_end_date: "",
    department: "",
    role_name: "",
    manager_name: "",
    primary_work_location: "",
    pay_cycle_reference: "",
    status: "onboarding",
    status_reason: "",
    note: "",
  };
}


function createEmptyWorkRightsDraft(): WorkRightsDraft {
  return {
    engagement_id: "",
    work_rights_basis: "australian_citizen",
    review_status: "verified",
    visa_subclass: "",
    visa_label: "",
    visa_grant_date: "",
    visa_expiry_date: "",
    work_condition_summary: "",
    hours_restriction_summary: "",
    sponsorship_required: false,
    sponsoring_entity_note: "",
    vevo_checked_at: "",
    next_review_due_at: "",
    reviewer_user_id: "",
    review_note: "",
  };
}


function createEmptyCompensationDraft(): CompensationDraft {
  return {
    remuneration_basis: "salary",
    expected_base_amount: "",
    tax_profile: "",
    superannuation_category: "",
    workers_comp_category: "",
    payroll_tax_in_scope: false,
    leave_profile: "",
    reimbursement_allowed: false,
    asset_issue_allowed: false,
    expense_account_id: "",
    liability_account_id: "",
    tfn_declaration_received: false,
    super_choice_received: false,
    abn_provided: false,
    gst_registered_known: false,
    note: "",
  };
}


function createEmptyLeaveSnapshotDraft(): LeaveSnapshotDraft {
  return {
    snapshot_date: todayIso(),
    annual_leave_hours: "0.00",
    personal_leave_hours: "0.00",
    long_service_leave_hours: "0.00",
    leave_value_amount: "0.00",
    current_lsl_value_amount: "0.00",
    non_current_lsl_value_amount: "0.00",
    note: "",
    reviewed_by_user_id: "",
  };
}


function createEmptyReimbursementDraft(): ReimbursementDraft {
  return {
    engagement_id: "",
    reimbursement_date: todayIso(),
    description: "",
    amount: "0.00",
    status: "draft",
    note: "",
  };
}


function createEmptyIssuedAssetDraft(): IssuedAssetDraft {
  return {
    engagement_id: "",
    asset_name: "",
    asset_type: "",
    serial_number: "",
    assigned_on: todayIso(),
    due_back_on: "",
    returned_on: "",
    status: "issued",
    note: "",
  };
}


function labelize(value: string | null | undefined) {
  return (value ?? "-").replaceAll("_", " ");
}


export function EmploymentSection({ operator }: { operator: OperatorState }) {
  const { selectedCompanyId, request, runAction, showMessage, documents, downloadFromApi, confirmDanger, refreshAll } = operator;
  const [dashboard, setDashboard] = useState<EmploymentDashboard | null>(null);
  const [workers, setWorkers] = useState<EmploymentWorker[]>([]);
  const [workerDetail, setWorkerDetail] = useState<EmploymentWorkerDetail | null>(null);
  const [headcountReport, setHeadcountReport] = useState<HeadcountReport | null>(null);
  const [workRightsReport, setWorkRightsReport] = useState<WorkRightsReport | null>(null);
  const [leaveLiabilityReport, setLeaveLiabilityReport] = useState<LeaveLiabilityReport | null>(null);
  const [contractorReviewReport, setContractorReviewReport] = useState<ContractorReviewReport | null>(null);
  const [selectedWorkerId, setSelectedWorkerId] = useState("");
  const [selectedEngagementId, setSelectedEngagementId] = useState("");
  const [selectedWorkRightsId, setSelectedWorkRightsId] = useState("");
  const [selectedLeaveSnapshotId, setSelectedLeaveSnapshotId] = useState("");
  const [selectedReimbursementId, setSelectedReimbursementId] = useState("");
  const [selectedIssuedAssetId, setSelectedIssuedAssetId] = useState("");
  const [workerDraft, setWorkerDraft] = useState<WorkerDraft>(createEmptyWorkerDraft());
  const [engagementDraft, setEngagementDraft] = useState<EngagementDraft>(createEmptyEngagementDraft());
  const [workRightsDraft, setWorkRightsDraft] = useState<WorkRightsDraft>(createEmptyWorkRightsDraft());
  const [compensationDraft, setCompensationDraft] = useState<CompensationDraft>(createEmptyCompensationDraft());
  const [leaveSnapshotDraft, setLeaveSnapshotDraft] = useState<LeaveSnapshotDraft>(createEmptyLeaveSnapshotDraft());
  const [reimbursementDraft, setReimbursementDraft] = useState<ReimbursementDraft>(createEmptyReimbursementDraft());
  const [issuedAssetDraft, setIssuedAssetDraft] = useState<IssuedAssetDraft>(createEmptyIssuedAssetDraft());
  const [existingDocumentId, setExistingDocumentId] = useState("");
  const [documentLinkNote, setDocumentLinkNote] = useState("");
  const [uploadDocumentNote, setUploadDocumentNote] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const requestRef = useRef(request);
  const runActionRef = useRef(runAction);
  const selectedWorkerIdRef = useRef(selectedWorkerId);

  useEffect(() => {
    requestRef.current = request;
    runActionRef.current = runAction;
  }, [request, runAction]);

  useEffect(() => {
    selectedWorkerIdRef.current = selectedWorkerId;
  }, [selectedWorkerId]);

  const availableDocumentOptions = useMemo(
    () => documents.map((item) => ({ value: item.id, label: `${item.original_filename} · ${formatDateTime(item.created_at)}` })),
    [documents],
  );

  const selectedEngagement = workerDetail?.engagements.find((item) => item.id === selectedEngagementId) ?? null;
  const selectedWorkRights = workerDetail?.work_rights_records.find((item) => item.id === selectedWorkRightsId) ?? null;
  const selectedCompensation = workerDetail?.compensation_profiles.find((item) => item.engagement_id === selectedEngagementId) ?? null;
  const selectedLeaveSnapshot = workerDetail?.leave_snapshots.find((item) => item.id === selectedLeaveSnapshotId) ?? null;
  const selectedReimbursement = workerDetail?.reimbursements.find((item) => item.id === selectedReimbursementId) ?? null;
  const selectedIssuedAsset = workerDetail?.issued_assets.find((item) => item.id === selectedIssuedAssetId) ?? null;

  const clearEmploymentState = useCallback(() => {
    setDashboard(null);
    setWorkers([]);
    setWorkerDetail(null);
    setHeadcountReport(null);
    setWorkRightsReport(null);
    setLeaveLiabilityReport(null);
    setContractorReviewReport(null);
    setSelectedWorkerId("");
    setSelectedEngagementId("");
    setSelectedWorkRightsId("");
    setSelectedLeaveSnapshotId("");
    setSelectedReimbursementId("");
    setSelectedIssuedAssetId("");
    setWorkerDraft(createEmptyWorkerDraft());
    setEngagementDraft(createEmptyEngagementDraft());
    setWorkRightsDraft(createEmptyWorkRightsDraft());
    setCompensationDraft(createEmptyCompensationDraft());
    setLeaveSnapshotDraft(createEmptyLeaveSnapshotDraft());
    setReimbursementDraft(createEmptyReimbursementDraft());
    setIssuedAssetDraft(createEmptyIssuedAssetDraft());
    setExistingDocumentId("");
    setDocumentLinkNote("");
    setUploadDocumentNote("");
    setUploadFile(null);
  }, []);

  const refreshEmploymentWorkspace = useCallback(async (preferredWorkerId?: string) => {
    if (!selectedCompanyId) {
      clearEmploymentState();
      return;
    }

    const [dashboardResult, workerResult, headcountResult, workRightsResult, leaveLiabilityResult, contractorReviewResult] = await Promise.all([
      requestRef.current<EmploymentDashboard>(`/api/companies/${selectedCompanyId}/employment/dashboard`),
      requestRef.current<EmploymentWorker[]>(`/api/companies/${selectedCompanyId}/employment/workers`),
      requestRef.current<HeadcountReport>(`/api/companies/${selectedCompanyId}/employment/reports/headcount`),
      requestRef.current<WorkRightsReport>(`/api/companies/${selectedCompanyId}/employment/reports/work-rights`),
      requestRef.current<LeaveLiabilityReport>(`/api/companies/${selectedCompanyId}/employment/reports/leave-liability-support`),
      requestRef.current<ContractorReviewReport>(`/api/companies/${selectedCompanyId}/employment/reports/contractor-review`),
    ]);

    setDashboard(dashboardResult);
    setWorkers(workerResult);
    setHeadcountReport(headcountResult);
    setWorkRightsReport(workRightsResult);
    setLeaveLiabilityReport(leaveLiabilityResult);
    setContractorReviewReport(contractorReviewResult);

    const currentSelectedWorkerId = selectedWorkerIdRef.current;
    const nextWorkerId = preferredWorkerId && workerResult.some((item) => item.id === preferredWorkerId)
      ? preferredWorkerId
      : workerResult.some((item) => item.id === currentSelectedWorkerId)
        ? currentSelectedWorkerId
        : workerResult[0]?.id ?? "";

    setSelectedWorkerId(nextWorkerId);
    if (!nextWorkerId) {
      setWorkerDetail(null);
    }
  }, [clearEmploymentState, selectedCompanyId]);

  const loadWorkerDetail = useCallback(async (workerId: string) => {
    if (!selectedCompanyId || !workerId) {
      setWorkerDetail(null);
      return;
    }
    const detail = await requestRef.current<EmploymentWorkerDetail>(`/api/companies/${selectedCompanyId}/employment/workers/${workerId}`);
    setWorkerDetail(detail);
  }, [selectedCompanyId]);

  useEffect(() => {
    if (!selectedCompanyId) {
      clearEmploymentState();
      return;
    }
    void runActionRef.current("Loading employment workspace", async () => {
      await refreshEmploymentWorkspace();
    });
  }, [clearEmploymentState, refreshEmploymentWorkspace, selectedCompanyId]);

  useEffect(() => {
    if (!selectedCompanyId || !selectedWorkerId) {
      setWorkerDetail(null);
      return;
    }
    if (workerDetail?.id === selectedWorkerId) {
      return;
    }
    void runActionRef.current("Loading employment worker", async () => {
      await loadWorkerDetail(selectedWorkerId);
    });
  }, [loadWorkerDetail, selectedCompanyId, selectedWorkerId, workerDetail?.id]);

  useEffect(() => {
    if (!workerDetail) {
      setWorkerDraft(createEmptyWorkerDraft());
      return;
    }
    setWorkerDraft({
      worker_code: workerDetail.worker_code,
      display_name: workerDetail.display_name,
      legal_name: workerDetail.legal_name ?? "",
      worker_kind: workerDetail.worker_kind,
      date_of_birth: workerDetail.date_of_birth ?? "",
      primary_email: workerDetail.primary_email ?? "",
      primary_phone: workerDetail.primary_phone ?? "",
      address_summary: workerDetail.address_summary ?? "",
      emergency_contact_summary: workerDetail.emergency_contact_summary ?? "",
      privacy_note: workerDetail.privacy_note ?? "",
      is_active: workerDetail.is_active,
      note: workerDetail.note ?? "",
    });
  }, [workerDetail]);

  useEffect(() => {
    const nextEngagementId = workerDetail?.engagements.some((item) => item.id === selectedEngagementId)
      ? selectedEngagementId
      : workerDetail?.engagements[0]?.id ?? "";
    setSelectedEngagementId(nextEngagementId);
  }, [workerDetail?.engagements, selectedEngagementId]);

  useEffect(() => {
    const nextWorkRightsId = workerDetail?.work_rights_records.some((item) => item.id === selectedWorkRightsId)
      ? selectedWorkRightsId
      : workerDetail?.work_rights_records[0]?.id ?? "";
    setSelectedWorkRightsId(nextWorkRightsId);
  }, [workerDetail?.work_rights_records, selectedWorkRightsId]);

  useEffect(() => {
    const nextLeaveSnapshotId = workerDetail?.leave_snapshots.some((item) => item.id === selectedLeaveSnapshotId)
      ? selectedLeaveSnapshotId
      : workerDetail?.leave_snapshots[0]?.id ?? "";
    setSelectedLeaveSnapshotId(nextLeaveSnapshotId);
  }, [workerDetail?.leave_snapshots, selectedLeaveSnapshotId]);

  useEffect(() => {
    const nextReimbursementId = workerDetail?.reimbursements.some((item) => item.id === selectedReimbursementId)
      ? selectedReimbursementId
      : workerDetail?.reimbursements[0]?.id ?? "";
    setSelectedReimbursementId(nextReimbursementId);
  }, [workerDetail?.reimbursements, selectedReimbursementId]);

  useEffect(() => {
    const nextIssuedAssetId = workerDetail?.issued_assets.some((item) => item.id === selectedIssuedAssetId)
      ? selectedIssuedAssetId
      : workerDetail?.issued_assets[0]?.id ?? "";
    setSelectedIssuedAssetId(nextIssuedAssetId);
  }, [workerDetail?.issued_assets, selectedIssuedAssetId]);

  useEffect(() => {
    if (!selectedEngagement) {
      setEngagementDraft(createEmptyEngagementDraft());
      return;
    }
    setEngagementDraft({
      engagement_type: selectedEngagement.engagement_type,
      employment_basis: selectedEngagement.employment_basis,
      start_date: selectedEngagement.start_date,
      expected_end_date: selectedEngagement.expected_end_date ?? "",
      actual_end_date: selectedEngagement.actual_end_date ?? "",
      department: selectedEngagement.department ?? "",
      role_name: selectedEngagement.role_name,
      manager_name: selectedEngagement.manager_name ?? "",
      primary_work_location: selectedEngagement.primary_work_location ?? "",
      pay_cycle_reference: selectedEngagement.pay_cycle_reference ?? "",
      status: selectedEngagement.status,
      status_reason: selectedEngagement.status_reason ?? "",
      note: selectedEngagement.note ?? "",
    });
  }, [selectedEngagement]);

  useEffect(() => {
    if (!selectedWorkRights) {
      setWorkRightsDraft((current) => ({ ...createEmptyWorkRightsDraft(), engagement_id: selectedEngagementId }));
      return;
    }
    setWorkRightsDraft({
      engagement_id: selectedWorkRights.engagement_id ?? "",
      work_rights_basis: selectedWorkRights.work_rights_basis,
      review_status: selectedWorkRights.review_status,
      visa_subclass: selectedWorkRights.visa_subclass ?? "",
      visa_label: selectedWorkRights.visa_label ?? "",
      visa_grant_date: selectedWorkRights.visa_grant_date ?? "",
      visa_expiry_date: selectedWorkRights.visa_expiry_date ?? "",
      work_condition_summary: selectedWorkRights.work_condition_summary ?? "",
      hours_restriction_summary: selectedWorkRights.hours_restriction_summary ?? "",
      sponsorship_required: selectedWorkRights.sponsorship_required,
      sponsoring_entity_note: selectedWorkRights.sponsoring_entity_note ?? "",
      vevo_checked_at: selectedWorkRights.vevo_checked_at ? selectedWorkRights.vevo_checked_at.slice(0, 10) : "",
      next_review_due_at: selectedWorkRights.next_review_due_at ?? "",
      reviewer_user_id: selectedWorkRights.reviewer_user_id ?? "",
      review_note: selectedWorkRights.review_note ?? "",
    });
  }, [selectedWorkRights, selectedEngagementId]);

  useEffect(() => {
    if (!selectedCompensation) {
      setCompensationDraft(createEmptyCompensationDraft());
      return;
    }
    setCompensationDraft({
      remuneration_basis: selectedCompensation.remuneration_basis,
      expected_base_amount: selectedCompensation.expected_base_amount ?? "",
      tax_profile: selectedCompensation.tax_profile ?? "",
      superannuation_category: selectedCompensation.superannuation_category ?? "",
      workers_comp_category: selectedCompensation.workers_comp_category ?? "",
      payroll_tax_in_scope: selectedCompensation.payroll_tax_in_scope,
      leave_profile: selectedCompensation.leave_profile ?? "",
      reimbursement_allowed: selectedCompensation.reimbursement_allowed,
      asset_issue_allowed: selectedCompensation.asset_issue_allowed,
      expense_account_id: selectedCompensation.expense_account_id ?? "",
      liability_account_id: selectedCompensation.liability_account_id ?? "",
      tfn_declaration_received: selectedCompensation.tfn_declaration_received,
      super_choice_received: selectedCompensation.super_choice_received,
      abn_provided: selectedCompensation.abn_provided,
      gst_registered_known: selectedCompensation.gst_registered_known,
      note: selectedCompensation.note ?? "",
    });
  }, [selectedCompensation]);

  useEffect(() => {
    if (!selectedLeaveSnapshot) {
      setLeaveSnapshotDraft(createEmptyLeaveSnapshotDraft());
      return;
    }
    setLeaveSnapshotDraft({
      snapshot_date: selectedLeaveSnapshot.snapshot_date,
      annual_leave_hours: selectedLeaveSnapshot.annual_leave_hours,
      personal_leave_hours: selectedLeaveSnapshot.personal_leave_hours,
      long_service_leave_hours: selectedLeaveSnapshot.long_service_leave_hours,
      leave_value_amount: selectedLeaveSnapshot.leave_value_amount,
      current_lsl_value_amount: selectedLeaveSnapshot.current_lsl_value_amount,
      non_current_lsl_value_amount: selectedLeaveSnapshot.non_current_lsl_value_amount,
      note: selectedLeaveSnapshot.note ?? "",
      reviewed_by_user_id: selectedLeaveSnapshot.reviewed_by_user_id ?? "",
    });
  }, [selectedLeaveSnapshot]);

  useEffect(() => {
    if (!selectedReimbursement) {
      setReimbursementDraft((current) => ({ ...createEmptyReimbursementDraft(), engagement_id: selectedEngagementId || current.engagement_id }));
      return;
    }
    setReimbursementDraft({
      engagement_id: selectedReimbursement.engagement_id ?? "",
      reimbursement_date: selectedReimbursement.reimbursement_date,
      description: selectedReimbursement.description,
      amount: selectedReimbursement.amount,
      status: selectedReimbursement.status,
      note: selectedReimbursement.note ?? "",
    });
  }, [selectedReimbursement, selectedEngagementId]);

  useEffect(() => {
    if (!selectedIssuedAsset) {
      setIssuedAssetDraft((current) => ({ ...createEmptyIssuedAssetDraft(), engagement_id: selectedEngagementId || current.engagement_id }));
      return;
    }
    setIssuedAssetDraft({
      engagement_id: selectedIssuedAsset.engagement_id ?? "",
      asset_name: selectedIssuedAsset.asset_name,
      asset_type: selectedIssuedAsset.asset_type ?? "",
      serial_number: selectedIssuedAsset.serial_number ?? "",
      assigned_on: selectedIssuedAsset.assigned_on,
      due_back_on: selectedIssuedAsset.due_back_on ?? "",
      returned_on: selectedIssuedAsset.returned_on ?? "",
      status: selectedIssuedAsset.status,
      note: selectedIssuedAsset.note ?? "",
    });
  }, [selectedIssuedAsset, selectedEngagementId]);

  const queueGroups: Array<{ title: string; items: EmploymentQueueItem[] }> = [
    { title: "Onboarding", items: dashboard?.onboarding_items ?? [] },
    { title: "Work-rights review", items: dashboard?.work_rights_due_items ?? [] },
    { title: "Finalisation", items: dashboard?.finalization_items ?? [] },
  ];

  const saveWorker = () => {
    if (!selectedCompanyId) {
      return;
    }
    const payload = {
      worker_code: workerDraft.worker_code,
      display_name: workerDraft.display_name,
      legal_name: emptyToNull(workerDraft.legal_name),
      worker_kind: workerDraft.worker_kind,
      date_of_birth: emptyToNull(workerDraft.date_of_birth),
      primary_email: emptyToNull(workerDraft.primary_email),
      primary_phone: emptyToNull(workerDraft.primary_phone),
      address_summary: emptyToNull(workerDraft.address_summary),
      emergency_contact_summary: emptyToNull(workerDraft.emergency_contact_summary),
      privacy_note: emptyToNull(workerDraft.privacy_note),
      is_active: workerDraft.is_active,
      note: emptyToNull(workerDraft.note),
    };
    void runAction("Saving employment worker", async () => {
      if (selectedWorkerId && workerDetail) {
        const worker = await request<EmploymentWorker>(`/api/companies/${selectedCompanyId}/employment/workers/${selectedWorkerId}`, "PUT", payload);
        showMessage("success", `Updated ${worker.display_name}.`);
        await refreshEmploymentWorkspace(worker.id);
      } else {
        const worker = await request<EmploymentWorker>(`/api/companies/${selectedCompanyId}/employment/workers`, "POST", payload);
        showMessage("success", `Created ${worker.display_name}.`);
        await refreshEmploymentWorkspace(worker.id);
      }
    });
  };

  const saveEngagement = () => {
    if (!selectedCompanyId || !selectedWorkerId) {
      return;
    }
    const payload = {
      engagement_type: engagementDraft.engagement_type,
      employment_basis: engagementDraft.employment_basis,
      start_date: engagementDraft.start_date,
      expected_end_date: emptyToNull(engagementDraft.expected_end_date),
      actual_end_date: emptyToNull(engagementDraft.actual_end_date),
      department: emptyToNull(engagementDraft.department),
      role_name: engagementDraft.role_name,
      manager_name: emptyToNull(engagementDraft.manager_name),
      primary_work_location: emptyToNull(engagementDraft.primary_work_location),
      pay_cycle_reference: emptyToNull(engagementDraft.pay_cycle_reference),
      status: engagementDraft.status,
      status_reason: emptyToNull(engagementDraft.status_reason),
      note: emptyToNull(engagementDraft.note),
    };
    void runAction("Saving employment engagement", async () => {
      if (selectedEngagementId && selectedEngagement) {
        const engagement = await request<EmploymentEngagement>(`/api/companies/${selectedCompanyId}/employment/engagements/${selectedEngagementId}`, "PUT", payload);
        showMessage("success", `Saved engagement ${engagement.role_name}.`);
        await refreshEmploymentWorkspace(selectedWorkerId);
        setSelectedEngagementId(engagement.id);
      } else {
        const engagement = await request<EmploymentEngagement>(`/api/companies/${selectedCompanyId}/employment/workers/${selectedWorkerId}/engagements`, "POST", payload);
        showMessage("success", `Created engagement ${engagement.role_name}.`);
        await refreshEmploymentWorkspace(selectedWorkerId);
        setSelectedEngagementId(engagement.id);
      }
    });
  };

  const saveWorkRights = () => {
    if (!selectedCompanyId || !selectedWorkerId) {
      return;
    }
    const payload = {
      engagement_id: emptyToNull(workRightsDraft.engagement_id),
      work_rights_basis: workRightsDraft.work_rights_basis,
      review_status: workRightsDraft.review_status,
      visa_subclass: emptyToNull(workRightsDraft.visa_subclass),
      visa_label: emptyToNull(workRightsDraft.visa_label),
      visa_grant_date: emptyToNull(workRightsDraft.visa_grant_date),
      visa_expiry_date: emptyToNull(workRightsDraft.visa_expiry_date),
      work_condition_summary: emptyToNull(workRightsDraft.work_condition_summary),
      hours_restriction_summary: emptyToNull(workRightsDraft.hours_restriction_summary),
      sponsorship_required: workRightsDraft.sponsorship_required,
      sponsoring_entity_note: emptyToNull(workRightsDraft.sponsoring_entity_note),
      vevo_checked_at: emptyToNull(workRightsDraft.vevo_checked_at),
      next_review_due_at: emptyToNull(workRightsDraft.next_review_due_at),
      reviewer_user_id: emptyToNull(workRightsDraft.reviewer_user_id),
      review_note: emptyToNull(workRightsDraft.review_note),
    };
    void runAction("Saving work-rights record", async () => {
      if (selectedWorkRightsId && selectedWorkRights) {
        const record = await request<EmploymentWorkRights>(`/api/companies/${selectedCompanyId}/employment/work-rights/${selectedWorkRightsId}`, "PUT", payload);
        showMessage("success", "Saved work-rights review record.");
        await refreshEmploymentWorkspace(selectedWorkerId);
        setSelectedWorkRightsId(record.id);
      } else {
        const record = await request<EmploymentWorkRights>(`/api/companies/${selectedCompanyId}/employment/workers/${selectedWorkerId}/work-rights`, "POST", payload);
        showMessage("success", "Created work-rights review record.");
        await refreshEmploymentWorkspace(selectedWorkerId);
        setSelectedWorkRightsId(record.id);
      }
    });
  };

  const saveCompensation = () => {
    if (!selectedCompanyId || !selectedEngagementId) {
      return;
    }
    const payload = {
      remuneration_basis: compensationDraft.remuneration_basis,
      expected_base_amount: emptyToNull(compensationDraft.expected_base_amount),
      tax_profile: emptyToNull(compensationDraft.tax_profile),
      superannuation_category: emptyToNull(compensationDraft.superannuation_category),
      workers_comp_category: emptyToNull(compensationDraft.workers_comp_category),
      payroll_tax_in_scope: compensationDraft.payroll_tax_in_scope,
      leave_profile: emptyToNull(compensationDraft.leave_profile),
      reimbursement_allowed: compensationDraft.reimbursement_allowed,
      asset_issue_allowed: compensationDraft.asset_issue_allowed,
      expense_account_id: emptyToNull(compensationDraft.expense_account_id),
      liability_account_id: emptyToNull(compensationDraft.liability_account_id),
      tfn_declaration_received: compensationDraft.tfn_declaration_received,
      super_choice_received: compensationDraft.super_choice_received,
      abn_provided: compensationDraft.abn_provided,
      gst_registered_known: compensationDraft.gst_registered_known,
      note: emptyToNull(compensationDraft.note),
    };
    void runAction("Saving compensation profile", async () => {
      await request<EmploymentCompensation>(`/api/companies/${selectedCompanyId}/employment/engagements/${selectedEngagementId}/compensation`, "PUT", payload);
      showMessage("success", "Saved compensation profile.");
      await refreshEmploymentWorkspace(selectedWorkerId);
    });
  };

  const saveLeaveSnapshot = () => {
    if (!selectedCompanyId || !selectedEngagementId) {
      return;
    }
    const payload = {
      snapshot_date: leaveSnapshotDraft.snapshot_date,
      annual_leave_hours: leaveSnapshotDraft.annual_leave_hours,
      personal_leave_hours: leaveSnapshotDraft.personal_leave_hours,
      long_service_leave_hours: leaveSnapshotDraft.long_service_leave_hours,
      leave_value_amount: leaveSnapshotDraft.leave_value_amount,
      current_lsl_value_amount: leaveSnapshotDraft.current_lsl_value_amount,
      non_current_lsl_value_amount: leaveSnapshotDraft.non_current_lsl_value_amount,
      note: emptyToNull(leaveSnapshotDraft.note),
      reviewed_by_user_id: emptyToNull(leaveSnapshotDraft.reviewed_by_user_id),
    };
    void runAction("Saving leave snapshot", async () => {
      if (selectedLeaveSnapshotId && selectedLeaveSnapshot) {
        const snapshot = await request<EmploymentLeaveSnapshot>(`/api/companies/${selectedCompanyId}/employment/leave-snapshots/${selectedLeaveSnapshotId}`, "PUT", payload);
        showMessage("success", "Saved leave snapshot.");
        await refreshEmploymentWorkspace(selectedWorkerId);
        setSelectedLeaveSnapshotId(snapshot.id);
      } else {
        const snapshot = await request<EmploymentLeaveSnapshot>(`/api/companies/${selectedCompanyId}/employment/engagements/${selectedEngagementId}/leave-snapshots`, "POST", payload);
        showMessage("success", "Created leave snapshot.");
        await refreshEmploymentWorkspace(selectedWorkerId);
        setSelectedLeaveSnapshotId(snapshot.id);
      }
    });
  };

  const saveReimbursement = () => {
    if (!selectedCompanyId || !selectedWorkerId) {
      return;
    }
    const payload = {
      engagement_id: emptyToNull(reimbursementDraft.engagement_id),
      reimbursement_date: reimbursementDraft.reimbursement_date,
      description: reimbursementDraft.description,
      amount: reimbursementDraft.amount,
      status: reimbursementDraft.status,
      note: emptyToNull(reimbursementDraft.note),
    };
    void runAction("Saving reimbursement support", async () => {
      if (selectedReimbursementId && selectedReimbursement) {
        const reimbursement = await request<EmploymentReimbursement>(`/api/companies/${selectedCompanyId}/employment/reimbursements/${selectedReimbursementId}`, "PUT", payload);
        showMessage("success", "Saved reimbursement support item.");
        await refreshEmploymentWorkspace(selectedWorkerId);
        setSelectedReimbursementId(reimbursement.id);
      } else {
        const reimbursement = await request<EmploymentReimbursement>(`/api/companies/${selectedCompanyId}/employment/workers/${selectedWorkerId}/reimbursements`, "POST", payload);
        showMessage("success", "Created reimbursement support item.");
        await refreshEmploymentWorkspace(selectedWorkerId);
        setSelectedReimbursementId(reimbursement.id);
      }
    });
  };

  const saveIssuedAsset = () => {
    if (!selectedCompanyId || !selectedWorkerId) {
      return;
    }
    const payload = {
      engagement_id: emptyToNull(issuedAssetDraft.engagement_id),
      asset_name: issuedAssetDraft.asset_name,
      asset_type: emptyToNull(issuedAssetDraft.asset_type),
      serial_number: emptyToNull(issuedAssetDraft.serial_number),
      assigned_on: issuedAssetDraft.assigned_on,
      due_back_on: emptyToNull(issuedAssetDraft.due_back_on),
      returned_on: emptyToNull(issuedAssetDraft.returned_on),
      status: issuedAssetDraft.status,
      note: emptyToNull(issuedAssetDraft.note),
    };
    void runAction("Saving issued asset", async () => {
      if (selectedIssuedAssetId && selectedIssuedAsset) {
        const asset = await request<EmploymentIssuedAsset>(`/api/companies/${selectedCompanyId}/employment/issued-assets/${selectedIssuedAssetId}`, "PUT", payload);
        showMessage("success", "Saved issued asset record.");
        await refreshEmploymentWorkspace(selectedWorkerId);
        setSelectedIssuedAssetId(asset.id);
      } else {
        const asset = await request<EmploymentIssuedAsset>(`/api/companies/${selectedCompanyId}/employment/workers/${selectedWorkerId}/issued-assets`, "POST", payload);
        showMessage("success", "Created issued asset record.");
        await refreshEmploymentWorkspace(selectedWorkerId);
        setSelectedIssuedAssetId(asset.id);
      }
    });
  };

  const removeRecord = (label: string, path: string, successMessage: string) => {
    if (!selectedCompanyId || !selectedWorkerId || !confirmDanger(`Remove this ${label}? This will delete the current support record.`)) {
      return;
    }
    void runAction(`Removing ${label}`, async () => {
      await request(path, "DELETE", undefined, "void");
      showMessage("success", successMessage);
      await refreshEmploymentWorkspace(selectedWorkerId);
    });
  };

  const linkExistingDocument = () => {
    if (!selectedCompanyId || !selectedWorkerId || !existingDocumentId) {
      return;
    }
    void runAction("Linking employment document", async () => {
      await request(`/api/companies/${selectedCompanyId}/documents/${existingDocumentId}/links`, "POST", {
        entity_type: "employment_worker",
        entity_id: selectedWorkerId,
        note: emptyToNull(documentLinkNote),
      });
      showMessage("success", "Linked document to worker record.");
      setExistingDocumentId("");
      setDocumentLinkNote("");
      await refreshEmploymentWorkspace(selectedWorkerId);
    });
  };

  const uploadAndLinkDocument = () => {
    if (!selectedCompanyId || !selectedWorkerId || !uploadFile) {
      return;
    }
    void runAction("Uploading employment document", async () => {
      const formData = new FormData();
      formData.set("file", uploadFile);
      if (uploadDocumentNote.trim()) {
        formData.set("note", uploadDocumentNote.trim());
      }
      const uploaded = await request<{ id: string }>(`/api/companies/${selectedCompanyId}/documents`, "POST", formData);
      await request(`/api/companies/${selectedCompanyId}/documents/${uploaded.id}/links`, "POST", {
        entity_type: "employment_worker",
        entity_id: selectedWorkerId,
        note: emptyToNull(uploadDocumentNote),
      });
      await refreshAll();
      await refreshEmploymentWorkspace(selectedWorkerId);
      setUploadFile(null);
      setUploadDocumentNote("");
      showMessage("success", "Uploaded and linked employment evidence.");
    });
  };

  if (!selectedCompanyId) {
    return <EmptyState title="Select a company" detail="Choose a company in the sidebar to load employment records and review queues." />;
  }

  return (
    <section className="sections-stack">
      <article className="panel panel-wide">
        <div className="panel-heading">
          <h2>Employment dashboard and support reports</h2>
          <span className="pill">{dashboard?.total_workers ?? 0} workers</span>
        </div>
        <p className="summary-line">
          Internal calculation support only. This report does not lodge anything with the ATO and should be reviewed before manual form entry or submission.
        </p>
        <div className="workspace-split">
          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Snapshot</h3>
              <p className="summary-line">Total workers: <strong>{dashboard?.total_workers ?? 0}</strong></p>
              <p className="summary-line">Active engagements: <strong>{dashboard?.active_engagements ?? 0}</strong></p>
              <p className="summary-line">Onboarding queue: <strong>{dashboard?.onboarding_count ?? 0}</strong></p>
              <p className="summary-line">Work-rights follow-up: <strong>{dashboard?.expiring_work_rights_count ?? 0}</strong></p>
              <p className="summary-line">Workers missing linked evidence: <strong>{dashboard?.missing_document_count ?? 0}</strong></p>
            </div>

            <div className="mini-card">
              <h3>Reports and exports</h3>
              <p className="summary-line">Headcount rows: <strong>{headcountReport?.rows.length ?? 0}</strong></p>
              <p className="summary-line">Work-rights review rows: <strong>{workRightsReport?.rows.length ?? 0}</strong></p>
              <p className="summary-line">Leave liability rows: <strong>{leaveLiabilityReport?.rows.length ?? 0}</strong></p>
              <p className="summary-line">Contractor review rows: <strong>{contractorReviewReport?.rows.length ?? 0}</strong></p>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" onClick={() => runAction("Exporting employment headcount", async () => {
                  await downloadFromApi(`/api/companies/${selectedCompanyId}/employment/reports/headcount/export`, "employment-headcount.csv");
                })}>
                  Export headcount
                </button>
                <button className="button-link button-link-small" type="button" onClick={() => runAction("Exporting work-rights review", async () => {
                  await downloadFromApi(`/api/companies/${selectedCompanyId}/employment/reports/work-rights/export`, "employment-work-rights.csv");
                })}>
                  Export work-rights review
                </button>
                <button className="button-link button-link-small" type="button" onClick={() => runAction("Exporting leave liability support", async () => {
                  await downloadFromApi(`/api/companies/${selectedCompanyId}/employment/reports/leave-liability-support/export`, "employment-leave-liability-support.csv");
                })}>
                  Export leave liability
                </button>
                <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Exporting contractor review", async () => {
                  await downloadFromApi(`/api/companies/${selectedCompanyId}/employment/reports/contractor-review/export`, "employment-contractor-review.csv");
                })}>
                  Export contractor review
                </button>
              </div>
            </div>
          </div>

          <div className="stacked-cards">
            {queueGroups.map((group) => (
              <div key={group.title} className="mini-card">
                <h3>{group.title}</h3>
                {group.items.length ? (
                  <div className="compact-list">
                    {group.items.map((item) => (
                      <button key={`${group.title}-${item.worker_id}-${item.engagement_id ?? "none"}-${item.title}`} className={`list-row-button${selectedWorkerId === item.worker_id ? " is-active" : ""}`} type="button" onClick={() => setSelectedWorkerId(item.worker_id)}>
                        <strong>{item.worker_name}</strong>
                        <span>{item.title}</span>
                        <span>{item.due_date ? formatDate(item.due_date) : "No due date"}</span>
                        <StatusPill value={item.status} />
                      </button>
                    ))}
                  </div>
                ) : (
                  <EmptyState title={`No ${group.title.toLowerCase()} items`} detail="The current employment review queue is clear for this slice." />
                )}
              </div>
            ))}
          </div>
        </div>
      </article>

      <article className="panel panel-wide">
        <div className="panel-heading">
          <h2>Worker register, compliance, and traceability</h2>
          <span className="pill">{workerDetail ? workerDetail.display_name : "new worker"}</span>
        </div>
        <div className="workspace-split">
          <div className="stacked-cards">
            <div className="mini-card">
              <div className="panel-heading">
                <h3>Workers</h3>
                <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => {
                  setSelectedWorkerId("");
                  setWorkerDetail(null);
                  setWorkerDraft(createEmptyWorkerDraft());
                }}>
                  New worker
                </button>
              </div>
              <div className="compact-list tall-list">
                {workers.map((item) => (
                  <button key={item.id} className={`list-row-button${selectedWorkerId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedWorkerId(item.id)}>
                    <strong>{item.display_name}</strong>
                    <span>{item.worker_code} · {labelize(item.worker_kind)}</span>
                    <StatusPill value={item.is_active ? "active" : "archived"} />
                  </button>
                ))}
              </div>
              <div className="form-grid two-up">
                <Field label="Worker code"><input value={workerDraft.worker_code} onChange={(event) => setWorkerDraft((current) => ({ ...current, worker_code: event.target.value }))} /></Field>
                <Field label="Display name"><input value={workerDraft.display_name} onChange={(event) => setWorkerDraft((current) => ({ ...current, display_name: event.target.value }))} /></Field>
                <Field label="Legal name"><input value={workerDraft.legal_name} onChange={(event) => setWorkerDraft((current) => ({ ...current, legal_name: event.target.value }))} /></Field>
                <Field label="Worker kind"><select value={workerDraft.worker_kind} onChange={(event) => setWorkerDraft((current) => ({ ...current, worker_kind: event.target.value }))}>{WORKER_KIND_OPTIONS.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}</select></Field>
                <Field label="Date of birth"><input type="date" value={workerDraft.date_of_birth} onChange={(event) => setWorkerDraft((current) => ({ ...current, date_of_birth: event.target.value }))} /></Field>
                <Field label="Primary email"><input value={workerDraft.primary_email} onChange={(event) => setWorkerDraft((current) => ({ ...current, primary_email: event.target.value }))} /></Field>
                <Field label="Primary phone"><input value={workerDraft.primary_phone} onChange={(event) => setWorkerDraft((current) => ({ ...current, primary_phone: event.target.value }))} /></Field>
                <Field label="Active"><select value={workerDraft.is_active ? "true" : "false"} onChange={(event) => setWorkerDraft((current) => ({ ...current, is_active: event.target.value === "true" }))}><option value="true">Active</option><option value="false">Inactive</option></select></Field>
                <Field label="Address summary" wide><input value={workerDraft.address_summary} onChange={(event) => setWorkerDraft((current) => ({ ...current, address_summary: event.target.value }))} /></Field>
                <Field label="Emergency contact" wide><input value={workerDraft.emergency_contact_summary} onChange={(event) => setWorkerDraft((current) => ({ ...current, emergency_contact_summary: event.target.value }))} /></Field>
                <Field label="Privacy note" wide><input value={workerDraft.privacy_note} onChange={(event) => setWorkerDraft((current) => ({ ...current, privacy_note: event.target.value }))} /></Field>
                <Field label="Internal note" wide><input value={workerDraft.note} onChange={(event) => setWorkerDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" onClick={saveWorker}>Save worker</button>
              </div>
            </div>

            <div className="mini-card">
              <h3>Linked evidence</h3>
              {workerDetail ? (
                <>
                  <div className="compact-list">
                    {workerDetail.linked_documents.map((item) => (
                      <div key={item.link_id} className="list-row-button">
                        <strong>{item.original_filename}</strong>
                        <span>{item.note || "No note"}</span>
                        <span>{formatDateTime(item.linked_at)}</span>
                        <div className="request-actions">
                          <button className="button-link button-link-small" type="button" onClick={() => runAction("Downloading employment evidence", async () => {
                            await downloadFromApi(`/api/companies/${selectedCompanyId}/documents/${item.document_id}/download`, item.original_filename);
                          })}>Download</button>
                          <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => removeRecord("linked document", `/api/companies/${selectedCompanyId}/documents/${item.document_id}/links/${item.link_id}`, "Removed linked document.")}>Unlink</button>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="form-grid two-up">
                    <Field label="Existing document"><select value={existingDocumentId} onChange={(event) => setExistingDocumentId(event.target.value)}><option value="">Select document</option>{availableDocumentOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                    <Field label="Link note"><input value={documentLinkNote} onChange={(event) => setDocumentLinkNote(event.target.value)} /></Field>
                    <Field label="Upload evidence" wide><input type="file" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} /></Field>
                    <Field label="Upload note" wide><input value={uploadDocumentNote} onChange={(event) => setUploadDocumentNote(event.target.value)} /></Field>
                  </div>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={linkExistingDocument}>Link existing document</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" onClick={uploadAndLinkDocument}>Upload and link</button>
                  </div>
                </>
              ) : (
                <EmptyState title="No worker selected" detail="Select a worker to review linked visas, contracts, reimbursements, and other supporting evidence." />
              )}
            </div>
          </div>

          <div className="stacked-cards">
            <div className="mini-card">
              <div className="panel-heading"><h3>Engagements</h3>{workerDetail ? <StatusPill value={selectedEngagement?.status} /> : null}</div>
              {workerDetail ? (
                <>
                  <div className="compact-list tall-list">
                    {workerDetail.engagements.map((item) => (
                      <button key={item.id} className={`list-row-button${selectedEngagementId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedEngagementId(item.id)}>
                        <strong>{item.role_name}</strong>
                        <span>{labelize(item.engagement_type)} · {formatDate(item.start_date)}</span>
                        <StatusPill value={item.status} />
                      </button>
                    ))}
                  </div>
                  <div className="form-grid two-up">
                    <Field label="Engagement type"><select value={engagementDraft.engagement_type} onChange={(event) => setEngagementDraft((current) => ({ ...current, engagement_type: event.target.value }))}>{ENGAGEMENT_TYPE_OPTIONS.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}</select></Field>
                    <Field label="Employment basis"><input value={engagementDraft.employment_basis} onChange={(event) => setEngagementDraft((current) => ({ ...current, employment_basis: event.target.value }))} /></Field>
                    <Field label="Start date"><input type="date" value={engagementDraft.start_date} onChange={(event) => setEngagementDraft((current) => ({ ...current, start_date: event.target.value }))} /></Field>
                    <Field label="Expected end"><input type="date" value={engagementDraft.expected_end_date} onChange={(event) => setEngagementDraft((current) => ({ ...current, expected_end_date: event.target.value }))} /></Field>
                    <Field label="Actual end"><input type="date" value={engagementDraft.actual_end_date} onChange={(event) => setEngagementDraft((current) => ({ ...current, actual_end_date: event.target.value }))} /></Field>
                    <Field label="Status"><select value={engagementDraft.status} onChange={(event) => setEngagementDraft((current) => ({ ...current, status: event.target.value }))}>{EMPLOYMENT_STATUS_OPTIONS.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}</select></Field>
                    <Field label="Role name"><input value={engagementDraft.role_name} onChange={(event) => setEngagementDraft((current) => ({ ...current, role_name: event.target.value }))} /></Field>
                    <Field label="Department"><input value={engagementDraft.department} onChange={(event) => setEngagementDraft((current) => ({ ...current, department: event.target.value }))} /></Field>
                    <Field label="Manager"><input value={engagementDraft.manager_name} onChange={(event) => setEngagementDraft((current) => ({ ...current, manager_name: event.target.value }))} /></Field>
                    <Field label="Work location"><input value={engagementDraft.primary_work_location} onChange={(event) => setEngagementDraft((current) => ({ ...current, primary_work_location: event.target.value }))} /></Field>
                    <Field label="Pay cycle ref"><input value={engagementDraft.pay_cycle_reference} onChange={(event) => setEngagementDraft((current) => ({ ...current, pay_cycle_reference: event.target.value }))} /></Field>
                    <Field label="Status reason"><input value={engagementDraft.status_reason} onChange={(event) => setEngagementDraft((current) => ({ ...current, status_reason: event.target.value }))} /></Field>
                    <Field label="Internal note" wide><input value={engagementDraft.note} onChange={(event) => setEngagementDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                  </div>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={saveEngagement}>Save engagement</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => {
                      setSelectedEngagementId("");
                      setEngagementDraft(createEmptyEngagementDraft());
                    }}>New engagement</button>
                    {selectedEngagement ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => removeRecord("engagement", `/api/companies/${selectedCompanyId}/employment/engagements/${selectedEngagement.id}`, "Removed employment engagement.")}>Delete engagement</button> : null}
                  </div>
                </>
              ) : (
                <EmptyState title="No worker selected" detail="Pick a worker to capture engagement type, work location, status, and end-of-service dates." />
              )}
            </div>

            <div className="mini-card">
              <h3>Work-rights and compensation</h3>
              {workerDetail ? (
                <>
                  <div className="compact-list">
                    {workerDetail.work_rights_records.map((item) => (
                      <button key={item.id} className={`list-row-button${selectedWorkRightsId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedWorkRightsId(item.id)}>
                        <strong>{item.visa_label || labelize(item.work_rights_basis)}</strong>
                        <span>{item.next_review_due_at ? formatDate(item.next_review_due_at) : "No review date"}</span>
                        <StatusPill value={item.review_status} />
                      </button>
                    ))}
                  </div>
                  <div className="form-grid two-up">
                    <Field label="Engagement"><select value={workRightsDraft.engagement_id} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, engagement_id: event.target.value }))}><option value="">Worker-level</option>{workerDetail.engagements.map((item) => <option key={item.id} value={item.id}>{item.role_name}</option>)}</select></Field>
                    <Field label="Rights basis"><select value={workRightsDraft.work_rights_basis} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, work_rights_basis: event.target.value }))}>{WORK_RIGHTS_BASIS_OPTIONS.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}</select></Field>
                    <Field label="Review status"><select value={workRightsDraft.review_status} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, review_status: event.target.value }))}>{WORK_RIGHTS_STATUS_OPTIONS.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}</select></Field>
                    <Field label="Visa subclass"><input value={workRightsDraft.visa_subclass} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, visa_subclass: event.target.value }))} /></Field>
                    <Field label="Visa label"><input value={workRightsDraft.visa_label} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, visa_label: event.target.value }))} /></Field>
                    <Field label="Visa grant date"><input type="date" value={workRightsDraft.visa_grant_date} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, visa_grant_date: event.target.value }))} /></Field>
                    <Field label="Visa expiry date"><input type="date" value={workRightsDraft.visa_expiry_date} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, visa_expiry_date: event.target.value }))} /></Field>
                    <Field label="Next review due"><input type="date" value={workRightsDraft.next_review_due_at} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, next_review_due_at: event.target.value }))} /></Field>
                    <Field label="VEVO checked"><input type="date" value={workRightsDraft.vevo_checked_at} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, vevo_checked_at: event.target.value }))} /></Field>
                    <Field label="Sponsorship required"><select value={workRightsDraft.sponsorship_required ? "true" : "false"} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, sponsorship_required: event.target.value === "true" }))}><option value="false">No</option><option value="true">Yes</option></select></Field>
                    <Field label="Restrictions" wide><input value={workRightsDraft.hours_restriction_summary} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, hours_restriction_summary: event.target.value }))} /></Field>
                    <Field label="Conditions" wide><input value={workRightsDraft.work_condition_summary} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, work_condition_summary: event.target.value }))} /></Field>
                    <Field label="Sponsorship note" wide><input value={workRightsDraft.sponsoring_entity_note} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, sponsoring_entity_note: event.target.value }))} /></Field>
                    <Field label="Review note" wide><input value={workRightsDraft.review_note} onChange={(event) => setWorkRightsDraft((current) => ({ ...current, review_note: event.target.value }))} /></Field>
                  </div>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={saveWorkRights}>Save work-rights record</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => {
                      setSelectedWorkRightsId("");
                      setWorkRightsDraft({ ...createEmptyWorkRightsDraft(), engagement_id: selectedEngagementId });
                    }}>New rights record</button>
                    {selectedWorkRights ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => removeRecord("work-rights record", `/api/companies/${selectedCompanyId}/employment/work-rights/${selectedWorkRights.id}`, "Removed work-rights record.")}>Delete record</button> : null}
                  </div>

                  <div className="form-grid two-up">
                    <Field label="Remuneration basis"><select value={compensationDraft.remuneration_basis} onChange={(event) => setCompensationDraft((current) => ({ ...current, remuneration_basis: event.target.value }))}>{REMUNERATION_BASIS_OPTIONS.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}</select></Field>
                    <Field label="Expected base amount"><input value={compensationDraft.expected_base_amount} onChange={(event) => setCompensationDraft((current) => ({ ...current, expected_base_amount: event.target.value }))} /></Field>
                    <Field label="Tax profile"><input value={compensationDraft.tax_profile} onChange={(event) => setCompensationDraft((current) => ({ ...current, tax_profile: event.target.value }))} /></Field>
                    <Field label="Leave profile"><input value={compensationDraft.leave_profile} onChange={(event) => setCompensationDraft((current) => ({ ...current, leave_profile: event.target.value }))} /></Field>
                    <Field label="Super category"><input value={compensationDraft.superannuation_category} onChange={(event) => setCompensationDraft((current) => ({ ...current, superannuation_category: event.target.value }))} /></Field>
                    <Field label="Workers comp"><input value={compensationDraft.workers_comp_category} onChange={(event) => setCompensationDraft((current) => ({ ...current, workers_comp_category: event.target.value }))} /></Field>
                    <Field label="Expense account"><select value={compensationDraft.expense_account_id} onChange={(event) => setCompensationDraft((current) => ({ ...current, expense_account_id: event.target.value }))}><option value="">Select account</option>{operator.accountOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                    <Field label="Liability account"><select value={compensationDraft.liability_account_id} onChange={(event) => setCompensationDraft((current) => ({ ...current, liability_account_id: event.target.value }))}><option value="">Select account</option>{operator.accountOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                    <Field label="Payroll tax in scope"><select value={compensationDraft.payroll_tax_in_scope ? "true" : "false"} onChange={(event) => setCompensationDraft((current) => ({ ...current, payroll_tax_in_scope: event.target.value === "true" }))}><option value="false">No</option><option value="true">Yes</option></select></Field>
                    <Field label="Reimbursements allowed"><select value={compensationDraft.reimbursement_allowed ? "true" : "false"} onChange={(event) => setCompensationDraft((current) => ({ ...current, reimbursement_allowed: event.target.value === "true" }))}><option value="false">No</option><option value="true">Yes</option></select></Field>
                    <Field label="Assets allowed"><select value={compensationDraft.asset_issue_allowed ? "true" : "false"} onChange={(event) => setCompensationDraft((current) => ({ ...current, asset_issue_allowed: event.target.value === "true" }))}><option value="false">No</option><option value="true">Yes</option></select></Field>
                    <Field label="TFN declaration"><select value={compensationDraft.tfn_declaration_received ? "true" : "false"} onChange={(event) => setCompensationDraft((current) => ({ ...current, tfn_declaration_received: event.target.value === "true" }))}><option value="false">No</option><option value="true">Yes</option></select></Field>
                    <Field label="Super choice"><select value={compensationDraft.super_choice_received ? "true" : "false"} onChange={(event) => setCompensationDraft((current) => ({ ...current, super_choice_received: event.target.value === "true" }))}><option value="false">No</option><option value="true">Yes</option></select></Field>
                    <Field label="ABN provided"><select value={compensationDraft.abn_provided ? "true" : "false"} onChange={(event) => setCompensationDraft((current) => ({ ...current, abn_provided: event.target.value === "true" }))}><option value="false">No</option><option value="true">Yes</option></select></Field>
                    <Field label="GST known"><select value={compensationDraft.gst_registered_known ? "true" : "false"} onChange={(event) => setCompensationDraft((current) => ({ ...current, gst_registered_known: event.target.value === "true" }))}><option value="false">No</option><option value="true">Yes</option></select></Field>
                    <Field label="Compensation note" wide><input value={compensationDraft.note} onChange={(event) => setCompensationDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                  </div>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={saveCompensation} disabled={!selectedEngagementId}>Save compensation</button>
                    {selectedCompensation ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => removeRecord("compensation profile", `/api/companies/${selectedCompanyId}/employment/compensation/${selectedCompensation.id}`, "Removed compensation profile.")}>Delete compensation</button> : null}
                  </div>
                </>
              ) : (
                <EmptyState title="No worker selected" detail="Load a worker to capture work-rights evidence, compensation settings, and payroll support flags." />
              )}
            </div>

            <div className="mini-card">
              <h3>Leave snapshots, reimbursements, and assets</h3>
              {workerDetail ? (
                <>
                  <div className="compact-list">
                    {workerDetail.leave_snapshots.map((item) => (
                      <button key={item.id} className={`list-row-button${selectedLeaveSnapshotId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedLeaveSnapshotId(item.id)}>
                        <strong>{formatDate(item.snapshot_date)}</strong>
                        <span>{formatMoney(item.leave_value_amount)}</span>
                      </button>
                    ))}
                  </div>
                  <div className="form-grid two-up">
                    <Field label="Snapshot date"><input type="date" value={leaveSnapshotDraft.snapshot_date} onChange={(event) => setLeaveSnapshotDraft((current) => ({ ...current, snapshot_date: event.target.value }))} /></Field>
                    <Field label="Annual leave hours"><input value={leaveSnapshotDraft.annual_leave_hours} onChange={(event) => setLeaveSnapshotDraft((current) => ({ ...current, annual_leave_hours: event.target.value }))} /></Field>
                    <Field label="Personal leave hours"><input value={leaveSnapshotDraft.personal_leave_hours} onChange={(event) => setLeaveSnapshotDraft((current) => ({ ...current, personal_leave_hours: event.target.value }))} /></Field>
                    <Field label="Long service leave hours"><input value={leaveSnapshotDraft.long_service_leave_hours} onChange={(event) => setLeaveSnapshotDraft((current) => ({ ...current, long_service_leave_hours: event.target.value }))} /></Field>
                    <Field label="Leave value"><input value={leaveSnapshotDraft.leave_value_amount} onChange={(event) => setLeaveSnapshotDraft((current) => ({ ...current, leave_value_amount: event.target.value }))} /></Field>
                    <Field label="Current LSL value"><input value={leaveSnapshotDraft.current_lsl_value_amount} onChange={(event) => setLeaveSnapshotDraft((current) => ({ ...current, current_lsl_value_amount: event.target.value }))} /></Field>
                    <Field label="Non-current LSL value"><input value={leaveSnapshotDraft.non_current_lsl_value_amount} onChange={(event) => setLeaveSnapshotDraft((current) => ({ ...current, non_current_lsl_value_amount: event.target.value }))} /></Field>
                    <Field label="Leave note" wide><input value={leaveSnapshotDraft.note} onChange={(event) => setLeaveSnapshotDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                  </div>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={saveLeaveSnapshot} disabled={!selectedEngagementId}>Save leave snapshot</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => {
                      setSelectedLeaveSnapshotId("");
                      setLeaveSnapshotDraft(createEmptyLeaveSnapshotDraft());
                    }}>New snapshot</button>
                    {selectedLeaveSnapshot ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => removeRecord("leave snapshot", `/api/companies/${selectedCompanyId}/employment/leave-snapshots/${selectedLeaveSnapshot.id}`, "Removed leave snapshot.")}>Delete snapshot</button> : null}
                  </div>

                  <div className="compact-list">
                    {workerDetail.reimbursements.map((item) => (
                      <button key={item.id} className={`list-row-button${selectedReimbursementId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedReimbursementId(item.id)}>
                        <strong>{item.description}</strong>
                        <span>{formatMoney(item.amount)} · {formatDate(item.reimbursement_date)}</span>
                        <StatusPill value={item.status} />
                      </button>
                    ))}
                  </div>
                  <div className="form-grid two-up">
                    <Field label="Engagement"><select value={reimbursementDraft.engagement_id} onChange={(event) => setReimbursementDraft((current) => ({ ...current, engagement_id: event.target.value }))}><option value="">Worker-level</option>{workerDetail.engagements.map((item) => <option key={item.id} value={item.id}>{item.role_name}</option>)}</select></Field>
                    <Field label="Date"><input type="date" value={reimbursementDraft.reimbursement_date} onChange={(event) => setReimbursementDraft((current) => ({ ...current, reimbursement_date: event.target.value }))} /></Field>
                    <Field label="Description"><input value={reimbursementDraft.description} onChange={(event) => setReimbursementDraft((current) => ({ ...current, description: event.target.value }))} /></Field>
                    <Field label="Amount"><input value={reimbursementDraft.amount} onChange={(event) => setReimbursementDraft((current) => ({ ...current, amount: event.target.value }))} /></Field>
                    <Field label="Status"><select value={reimbursementDraft.status} onChange={(event) => setReimbursementDraft((current) => ({ ...current, status: event.target.value }))}>{REIMBURSEMENT_STATUS_OPTIONS.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}</select></Field>
                    <Field label="Note" wide><input value={reimbursementDraft.note} onChange={(event) => setReimbursementDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                  </div>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={saveReimbursement}>Save reimbursement</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => {
                      setSelectedReimbursementId("");
                      setReimbursementDraft({ ...createEmptyReimbursementDraft(), engagement_id: selectedEngagementId });
                    }}>New reimbursement</button>
                    {selectedReimbursement ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => removeRecord("reimbursement support item", `/api/companies/${selectedCompanyId}/employment/reimbursements/${selectedReimbursement.id}`, "Removed reimbursement support item.")}>Delete reimbursement</button> : null}
                  </div>

                  <div className="compact-list">
                    {workerDetail.issued_assets.map((item) => (
                      <button key={item.id} className={`list-row-button${selectedIssuedAssetId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedIssuedAssetId(item.id)}>
                        <strong>{item.asset_name}</strong>
                        <span>{item.serial_number || "No serial"}</span>
                        <StatusPill value={item.status} />
                      </button>
                    ))}
                  </div>
                  <div className="form-grid two-up">
                    <Field label="Engagement"><select value={issuedAssetDraft.engagement_id} onChange={(event) => setIssuedAssetDraft((current) => ({ ...current, engagement_id: event.target.value }))}><option value="">Worker-level</option>{workerDetail.engagements.map((item) => <option key={item.id} value={item.id}>{item.role_name}</option>)}</select></Field>
                    <Field label="Asset name"><input value={issuedAssetDraft.asset_name} onChange={(event) => setIssuedAssetDraft((current) => ({ ...current, asset_name: event.target.value }))} /></Field>
                    <Field label="Asset type"><input value={issuedAssetDraft.asset_type} onChange={(event) => setIssuedAssetDraft((current) => ({ ...current, asset_type: event.target.value }))} /></Field>
                    <Field label="Serial number"><input value={issuedAssetDraft.serial_number} onChange={(event) => setIssuedAssetDraft((current) => ({ ...current, serial_number: event.target.value }))} /></Field>
                    <Field label="Assigned on"><input type="date" value={issuedAssetDraft.assigned_on} onChange={(event) => setIssuedAssetDraft((current) => ({ ...current, assigned_on: event.target.value }))} /></Field>
                    <Field label="Due back"><input type="date" value={issuedAssetDraft.due_back_on} onChange={(event) => setIssuedAssetDraft((current) => ({ ...current, due_back_on: event.target.value }))} /></Field>
                    <Field label="Returned on"><input type="date" value={issuedAssetDraft.returned_on} onChange={(event) => setIssuedAssetDraft((current) => ({ ...current, returned_on: event.target.value }))} /></Field>
                    <Field label="Status"><select value={issuedAssetDraft.status} onChange={(event) => setIssuedAssetDraft((current) => ({ ...current, status: event.target.value }))}>{ASSET_STATUS_OPTIONS.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}</select></Field>
                    <Field label="Asset note" wide><input value={issuedAssetDraft.note} onChange={(event) => setIssuedAssetDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                  </div>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={saveIssuedAsset}>Save issued asset</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => {
                      setSelectedIssuedAssetId("");
                      setIssuedAssetDraft({ ...createEmptyIssuedAssetDraft(), engagement_id: selectedEngagementId });
                    }}>New asset</button>
                    {selectedIssuedAsset ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => removeRecord("issued asset", `/api/companies/${selectedCompanyId}/employment/issued-assets/${selectedIssuedAsset.id}`, "Removed issued asset record.")}>Delete asset</button> : null}
                  </div>
                </>
              ) : (
                <EmptyState title="No worker selected" detail="Select a worker to maintain leave snapshots, reimbursement support, and issued asset tracking." />
              )}
            </div>
          </div>
        </div>
      </article>
    </section>
  );
}