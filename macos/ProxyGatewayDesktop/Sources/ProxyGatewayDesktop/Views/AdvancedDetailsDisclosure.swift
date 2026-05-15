import SwiftUI

struct AdvancedDetailsDisclosure: View {
    @ObservedObject var store: MacVpnStore
    let viewState: MacVpnViewState
    @State private var isExpanded = false

    var body: some View {
        DisclosureGroup("诊断详情", isExpanded: $isExpanded) {
            VStack(alignment: .leading, spacing: 12) {
                Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 8) {
                    ForEach(viewState.detailRows) { row in
                        GridRow {
                            Text(row.label)
                                .foregroundStyle(.secondary)

                            Text(row.value.isEmpty ? "未知" : row.value)
                                .textSelection(.enabled)
                        }
                    }
                }

                CommandOutputView(result: store.lastResult)
            }
            .padding(.top, 8)
        }
    }
}
