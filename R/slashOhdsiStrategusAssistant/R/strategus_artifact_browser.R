#' Launch a local Shiny browser for a Strategus workflow directory
#'
#' The browser is read-only, uses the workflow artifact registry, does not
#' contact ACP/MCP or a database, and excludes connection configuration files.
#'
#' @param outputDir workflow output directory
#' @param host Shiny host; defaults to localhost for safety
#' @param port optional Shiny port
#' @param launch.browser whether to open a browser window
#' @export
launchStrategusArtifactBrowser <- function(outputDir,
                                           host = "127.0.0.1",
                                           port = NULL,
                                           launch.browser = interactive()) {
  if (!requireNamespace("shiny", quietly = TRUE)) {
    stop("The optional shiny package is required. Install it to use the Strategus artifact browser.")
  }
  base_dir <- normalizePath(outputDir, winslash = "/", mustWork = TRUE)
  project_state <- .studyAgentSlashReadProjectState(base_dir)
  registry <- .studyAgentSlashBuildArtifactRegistry(base_dir)
  registry_table <- .studyAgentSlashArtifactRegistryTable(registry, viewer = TRUE)
  unsafe_classes <- c("db_details_json", "execution_settings_json")
  safe_table <- registry_table[!(registry_table$artifact_class %in% unsafe_classes), , drop = FALSE]
  state_value <- function(value) if (is.null(value)) "" else as.character(value)
  state_summary <- data.frame(
    field = c("workflow_type", "study_intent", "ai_support_mode", "current_step"),
    value = c(
      state_value(project_state$workflow_type),
      state_value(project_state$study_context$study_intent),
      state_value(project_state$study_context$ai_support_mode %||% project_state$ai_support_mode),
      state_value(project_state$resume$current_step_id)
    ),
    stringsAsFactors = FALSE
  )
  preview_artifact <- function(id) {
    item <- registry[[as.character(id)]] %||% NULL
    if (is.null(item) || !isTRUE(item$exists) || item$artifact_class %in% unsafe_classes) {
      return("No safe preview is available for this artifact.")
    }
    path <- normalizePath(item$absolute_path, winslash = "/", mustWork = FALSE)
    if (!identical(path, base_dir) && !startsWith(path, paste0(base_dir, "/"))) {
      return("Artifact path is outside this workflow directory.")
    }
    if (dir.exists(path)) return(paste(utils::head(list.files(path, recursive = TRUE), 100L), collapse = "\n"))
    if (grepl("\\.csv$", path, ignore.case = TRUE)) {
      data <- .studyAgentSlashReadCsvSafe(path)
      if (is.null(data)) return("CSV preview could not be read.")
      return(paste(utils::capture.output(print(utils::head(data, 100L))), collapse = "\n"))
    }
    if (grepl("\\.json$", path, ignore.case = TRUE)) {
      data <- .studyAgentSlashReadJsonSafe(path, simplifyVector = FALSE)
      if (is.null(data)) return("JSON preview could not be read.")
      return(jsonlite::toJSON(data, pretty = TRUE, auto_unbox = TRUE))
    }
    "Preview is available for CSV, JSON, and directory artifacts only."
  }
  ui <- shiny::fluidPage(
    shiny::titlePanel("Strategus workflow artifacts"),
    shiny::tabsetPanel(
      shiny::tabPanel("Overview", shiny::tableOutput("overview")),
      shiny::tabPanel("Artifacts", shiny::fluidRow(
        shiny::column(6, shiny::selectInput("artifact", "Artifact", choices = safe_table$artifact_id)),
        shiny::column(6, shiny::h4("Selected artifact preview"), shiny::verbatimTextOutput("selected_artifact_preview"))
      )),
      shiny::tabPanel("All artifacts", shiny::tableOutput("artifacts")),
      shiny::tabPanel("Preview", shiny::verbatimTextOutput("preview")),
      shiny::tabPanel("Diagnostics", shiny::p("Run scripts/08_launch_diagnostics_explorer.R for the specialized CohortDiagnostics Explorer."))
    )
  )
  server <- function(input, output, session) {
    output$overview <- shiny::renderTable(state_summary, striped = TRUE)
    output$artifacts <- shiny::renderTable(safe_table, striped = TRUE)
    output$selected_artifact_preview <- shiny::renderText(preview_artifact(input$artifact))
    output$preview <- shiny::renderText(preview_artifact(input$artifact))
  }
  shiny::runApp(shiny::shinyApp(ui, server), host = host, port = port, launch.browser = launch.browser)
}
