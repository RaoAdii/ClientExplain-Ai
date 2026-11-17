import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  FileText,
  GitBranch,
  ShieldCheck,
  BookOpen,
  Check,
  Scale,
  FolderPlus,
} from "lucide-react";
import { Navbar, Footer } from "@/components/navigation";
import { Button } from "@/components/ui/button";
import { pageMetadata } from "@/lib/metadata";

export const metadata = pageMetadata(
  "Clearer legal processes, thoughtfully explained",
  "Start a legal process project. ClientExplain AI is building toward source-backed visual explanations with lawyer review.",
  "/",
);
export default function Home() {
  return (
    <>
      <Navbar />
      <main id="main">
        <section className="hero container">
          <div className="hero-copy">
            <p className="eyebrow">
              <span className="status-dot" /> A clearer way to explain legal
              processes
            </p>
            <h1>
              Turn complex legal processes into{" "}
              <span>clear visual explanations.</span>
            </h1>
            <p className="hero-description">
              Give every client a clearer picture of what comes next. Start with
              an organized project workspace, built for the way legal
              professionals review and explain their work.
            </p>
            <div className="hero-actions">
              <Button asChild>
                <Link href="/dashboard/projects">
                  Open your workspace <ArrowRight size={17} />
                </Link>
              </Button>
              <Link className="text-link" href="#workflow">
                Explore the workflow <ArrowUpRight size={16} />
              </Link>
            </div>
            <p className="release-note">
              <span className="small-tag">Foundation release</span> Project
              organization is available. AI generation is coming in a later
              release.
            </p>
          </div>
          <div
            className="workflow-preview"
            aria-label="Illustrative product workflow, not a generated legal process"
          >
            <div className="preview-top">
              <span>
                <Scale size={16} /> A clearer client conversation
              </span>
              <span className="preview-label">Workflow concept</span>
            </div>
            <div className="preview-body">
              <div className="preview-heading">
                <p className="eyebrow">From complexity to clarity</p>
                <h2>
                  One process.
                  <br />A shared understanding.
                </h2>
              </div>
              <div className="preview-step">
                <span className="step-number">01</span>
                <div>
                  <strong>Start with the context</strong>
                  <p>Organize the process and jurisdiction.</p>
                </div>
                <FileText size={19} />
              </div>
              <div className="step-connector" />
              <div className="preview-step">
                <span className="step-number">02</span>
                <div>
                  <strong>Make the stages clear</strong>
                  <p>Planned: source-backed visual workflows.</p>
                </div>
                <GitBranch size={19} />
              </div>
              <div className="step-connector" />
              <div className="preview-step emphasis">
                <span className="step-number">03</span>
                <div>
                  <strong>Keep professional oversight</strong>
                  <p>Every AI explanation requires review.</p>
                </div>
                <ShieldCheck size={19} />
              </div>
              <div className="preview-note">
                <span className="note-line" /> Designed to support a lawyer’s
                explanation.
              </div>
            </div>
          </div>
        </section>
        <section className="principle-strip">
          <div className="container strip-inner">
            <span>
              <ShieldCheck size={19} /> Professional review first
            </span>
            <span>
              <BookOpen size={19} /> Sources in context
            </span>
            <span>
              <GitBranch size={19} /> Clarity at every stage
            </span>
          </div>
        </section>
        <section className="section container" id="workflow">
          <div className="section-heading">
            <div>
              <p className="eyebrow">A considered workflow</p>
              <h2>
                Less explaining from scratch.
                <br />
                More room for the conversation.
              </h2>
            </div>
            <p>
              We are building a focused workspace that helps lawyers turn
              process knowledge into explanations clients can follow.
            </p>
          </div>
          <div className="feature-grid">
            <article className="feature-card">
              <FolderPlus />
              <span className="small-tag available">Available now</span>
              <h3>Give each process a home</h3>
              <p>
                Create projects, record the jurisdiction, and keep the purpose
                of each explanation in one place.
              </p>
              <Link className="text-link" href="/dashboard/projects">
                Start a project <ArrowRight size={16} />
              </Link>
            </article>
            <article className="feature-card">
              <GitBranch />
              <span className="small-tag">Planned</span>
              <h3>Build a visual explanation</h3>
              <p>
                Document analysis, source-backed stages, editable workflows, and
                stage illustrations are planned for future releases.
              </p>
            </article>
            <article className="feature-card">
              <ShieldCheck />
              <span className="small-tag">Planned</span>
              <h3>Review before you share</h3>
              <p>
                Lawyer approval, version history, and PDF or PNG exports will
                support a deliberate review process.
              </p>
            </article>
          </div>
        </section>
        <section className="review-section" id="principles">
          <div className="container review-inner">
            <div>
              <p className="eyebrow">Professional judgment stays central</p>
              <h2>
                An explanation tool.
                <br />
                Your expertise at the center.
              </h2>
              <p>
                AI output must never be mistaken for verified legal advice.
                ClientExplain AI is designed around that distinction from the
                beginning.
              </p>
            </div>
            <ul>
              <li>
                <Check size={19} />
                <div>
                  <strong>Review is a requirement</strong>
                  <p>
                    All generated explanations must be reviewed by a qualified
                    legal professional.
                  </p>
                </div>
              </li>
              <li>
                <Check size={19} />
                <div>
                  <strong>Context matters</strong>
                  <p>
                    Jurisdiction, source quality, and the facts of each matter
                    need individual consideration.
                  </p>
                </div>
              </li>
              <li>
                <Check size={19} />
                <div>
                  <strong>Start with non-confidential information</strong>
                  <p>
                    This foundation is for evaluation. Do not enter sensitive
                    client information.
                  </p>
                </div>
              </li>
            </ul>
          </div>
        </section>
        <section className="container closing">
          <div>
            <p className="eyebrow">Start with a well-organized project</p>
            <h2>Make space for a clearer explanation.</h2>
          </div>
          <Button asChild>
            <Link href="/dashboard/projects">
              Open your workspace <ArrowRight size={17} />
            </Link>
          </Button>
        </section>
      </main>
      <Footer />
    </>
  );
}
