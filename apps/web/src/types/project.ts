export type Project = {
  id: string;
  name: string;
  description: string;
  jurisdiction: string;
  review_status: "requires_review" | "in_review" | "approved";
  created_at: string;
  updated_at: string;
};
