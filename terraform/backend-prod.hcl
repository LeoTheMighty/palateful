# Production backend configuration
# Uses S3 for remote state with DynamoDB locking

bucket         = "palateful-terraform-state"
key            = "prod/terraform.tfstate"
region         = "us-east-1"
encrypt        = true
dynamodb_table = "palateful-terraform-locks"
