# ECR Repositories

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

variable "additional_repositories" {
  type        = list(string)
  default     = []
  description = "Additional ECR repository names (e.g. api, worker, migrator)"
}

resource "aws_ecr_repository" "parser" {
  name                 = "${var.project}-parser"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name        = "${var.project}-parser"
    Environment = var.environment
    Project     = var.project
  }
}

# Lifecycle policy to keep only recent images
resource "aws_ecr_lifecycle_policy" "parser" {
  repository = aws_ecr_repository.parser.name

  policy = jsonencode({
    # ecrkeep1 (2026-09-24). Replaces a single "keep last 10, tagStatus any"
    # rule that delivered about **two days** of history for every service.
    #
    # Measured 2026-09-24: all four repos' oldest image was 2026-09-22.
    # `tagStatus = "any"` counts untagged build layers alongside releases, and
    # only **5 of 15** images per repo were tagged — so two thirds of the
    # window was spent on cruft nobody wants.
    #
    # **Why a longer window alone cannot fix the parser.** It last ran
    # successfully 2026-04-22 and failed 2026-09-23: **154 days idle.** No
    # time-based window under ~180 days would have kept its known-good image,
    # and 180 days of *every* build is unaffordable. Time-based retention
    # solves the three services that deploy and run continuously; it
    # structurally cannot solve the parser, because **deploy cadence and run
    # cadence are unrelated there.** That is what rule 3 is for.
    rules = [
      {
        # 1 — Build cruft. Two thirds of stored images, wanted by nobody.
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        # 2 — PROTECTED.
        #
        # **ECR has no "keep" verb.** There is no rule that preserves an
        # image; every rule's only action is `expire`. Protection is
        # therefore expressed *by claiming the image with a higher-priority
        # rule that will not expire it* — an image is acted on by the
        # LOWEST-numbered rule it matches, so `known-good-*` is consumed
        # here and never reaches the 30-day rule below.
        #
        # Do not try to add a "keep" rule; it does not exist. If this looks
        # backwards, that is why.
        #
        # Bounded rather than infinite, answering "replace or accumulate?":
        # **accumulate, but keep only the last 3.** Infinite accumulation is
        # a slow leak; replace-on-write means one bad tagging event destroys
        # the last good image — and the tagger is exactly the thing that
        # might be wrong. Three survives a mistake and still bounds the
        # cost: for the parser post-ocrload1 that is ~6-9 GB, not ~33 GB.
        rulePriority = 2
        description  = "Keep the last 3 known-good images, whatever their age"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["known-good-*"]
          countType      = "imageCountMoreThan"
          countNumber    = 3
        }
        action = { type = "expire" }
      },
      {
        # 3 — Releases. Time, not count: a count means whatever the deploy
        # frequency makes it mean, which is how "keep last 10" became two days.
        rulePriority = 3
        description  = "Keep tagged images for 30 days"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["*"]
          countType      = "sinceImagePushed"
          countUnit      = "days"
          countNumber    = 30
        }
        action = { type = "expire" }
      },
    ]
  })
}

# Additional repositories (api, worker, migrator)
resource "aws_ecr_repository" "additional" {
  for_each             = toset(var.additional_repositories)
  name                 = "${var.project}/${each.value}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name        = "${var.project}/${each.value}"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_ecr_lifecycle_policy" "additional" {
  for_each   = toset(var.additional_repositories)
  repository = aws_ecr_repository.additional[each.value].name

  policy = jsonencode({
    # ecrkeep1 (2026-09-24). Replaces a single "keep last 10, tagStatus any"
    # rule that delivered about **two days** of history for every service.
    #
    # Measured 2026-09-24: all four repos' oldest image was 2026-09-22.
    # `tagStatus = "any"` counts untagged build layers alongside releases, and
    # only **5 of 15** images per repo were tagged — so two thirds of the
    # window was spent on cruft nobody wants.
    #
    # **Why a longer window alone cannot fix the parser.** It last ran
    # successfully 2026-04-22 and failed 2026-09-23: **154 days idle.** No
    # time-based window under ~180 days would have kept its known-good image,
    # and 180 days of *every* build is unaffordable. Time-based retention
    # solves the three services that deploy and run continuously; it
    # structurally cannot solve the parser, because **deploy cadence and run
    # cadence are unrelated there.** That is what rule 3 is for.
    rules = [
      {
        # 1 — Build cruft. Two thirds of stored images, wanted by nobody.
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        # 2 — PROTECTED.
        #
        # **ECR has no "keep" verb.** There is no rule that preserves an
        # image; every rule's only action is `expire`. Protection is
        # therefore expressed *by claiming the image with a higher-priority
        # rule that will not expire it* — an image is acted on by the
        # LOWEST-numbered rule it matches, so `known-good-*` is consumed
        # here and never reaches the 30-day rule below.
        #
        # Do not try to add a "keep" rule; it does not exist. If this looks
        # backwards, that is why.
        #
        # Bounded rather than infinite, answering "replace or accumulate?":
        # **accumulate, but keep only the last 3.** Infinite accumulation is
        # a slow leak; replace-on-write means one bad tagging event destroys
        # the last good image — and the tagger is exactly the thing that
        # might be wrong. Three survives a mistake and still bounds the
        # cost: for the parser post-ocrload1 that is ~6-9 GB, not ~33 GB.
        rulePriority = 2
        description  = "Keep the last 3 known-good images, whatever their age"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["known-good-*"]
          countType      = "imageCountMoreThan"
          countNumber    = 3
        }
        action = { type = "expire" }
      },
      {
        # 3 — Releases. Time, not count: a count means whatever the deploy
        # frequency makes it mean, which is how "keep last 10" became two days.
        rulePriority = 3
        description  = "Keep tagged images for 30 days"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["*"]
          countType      = "sinceImagePushed"
          countUnit      = "days"
          countNumber    = 30
        }
        action = { type = "expire" }
      },
    ]
  })
}

output "repository_url" {
  value = aws_ecr_repository.parser.repository_url
}

output "repository_arn" {
  value = aws_ecr_repository.parser.arn
}

output "repository_name" {
  value = aws_ecr_repository.parser.name
}

output "additional_repository_urls" {
  value = { for k, v in aws_ecr_repository.additional : k => v.repository_url }
}

output "additional_repository_arns" {
  value = { for k, v in aws_ecr_repository.additional : k => v.arn }
}
