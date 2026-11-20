"""Job endpoints (spec section 7).

POST /api/jobs                    - start a search job
GET  /api/jobs/{job_id}           - status, totals, errors
GET  /api/jobs/{job_id}/results   - cleaned records (partial while running)
GET  /api/jobs/{job_id}/export    - .xlsx download (only if completed and the source permits export)
POST /api/jobs/{job_id}/cancel    - cancel a running job
"""
from fastapi import APIRouter, HTTPException, Response, status

from app.models.schemas import BusinessRecord, JobCreate, JobInfo, JobStatus
from app.services import exporter, job_manager
from app.services.job_manager import Job

router = APIRouter()


def _get_or_404(job_id: str) -> Job:
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found. It may have expired.")
    return job


@router.post("", response_model=JobInfo, status_code=status.HTTP_202_ACCEPTED)
async def create_job(req: JobCreate) -> JobInfo:
    # async so the job task is created on the server's running event loop.
    try:
        job = job_manager.create_job(req)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This data source is disabled. It can only be enabled when collection and export are authorized.",
        ) from exc
    except job_manager.TooManyJobsError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    return job_manager.to_info(job)


@router.get("/{job_id}", response_model=JobInfo)
async def get_job(job_id: str) -> JobInfo:
    return job_manager.to_info(_get_or_404(job_id))


@router.get("/{job_id}/results", response_model=list[BusinessRecord])
async def get_results(job_id: str) -> list[BusinessRecord]:
    return list(_get_or_404(job_id).records)  # snapshot; the job may still be appending


@router.post("/{job_id}/cancel", response_model=JobInfo)
async def cancel_job(job_id: str) -> JobInfo:
    job = _get_or_404(job_id)
    if job.is_finished:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Job is already {job.status.value}.")
    job_manager.cancel_job(job_id)
    return job_manager.to_info(job)  # status flips to "cancelled" once the task winds down


@router.get(
    "/{job_id}/export",
    response_class=Response,
    responses={200: {"content": {exporter.XLSX_MEDIA_TYPE: {}}, "description": "Excel file"}},
)
async def export_job(job_id: str) -> Response:
    job = _get_or_404(job_id)
    if job.status is not JobStatus.COMPLETED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Export is only available for completed searches (this one is {job.status.value}).",
        )
    if not job.collector.export_allowed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Export is not permitted by this data source's licence."
        )
    filename = exporter.export_filename(job.category, job.location)
    return Response(
        content=exporter.build_workbook(job.records),
        media_type=exporter.XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
