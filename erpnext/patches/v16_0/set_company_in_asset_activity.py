from collections import defaultdict

import frappe


def execute():
	frappe.reload_doc("assets", "doctype", "asset_activity")

	asset_activity = frappe.qb.DocType("Asset Activity")
	company = frappe.qb.DocType("Company")
	asset = frappe.qb.DocType("Asset")

	missing_company = (asset_activity.company.isnull()) | (asset_activity.company == "")

	companies = frappe.qb.from_(company).select(company.name).run(pluck="name")

	if len(companies) == 1:
		(
			frappe.qb.update(asset_activity).set(asset_activity.company, companies[0]).where(missing_company)
		).run()
		return

	companies_with_assets = (
		frappe.qb.from_(asset)
		.select(asset.company)
		.distinct()
		.where(asset.company.isnotnull() & (asset.company != ""))
		.run(pluck="company")
	)

	for comp in companies_with_assets:
		assets_in_comp = frappe.qb.from_(asset).select(asset.name).where(asset.company == comp)
		(
			frappe.qb.update(asset_activity)
			.set(asset_activity.company, comp)
			.where(asset_activity.asset.isin(assets_in_comp) & missing_company)
		).run()

	deleted_assets = (
		frappe.qb.from_(asset_activity).select(asset_activity.asset).where(missing_company).distinct()
	).run(pluck="asset")

	if deleted_assets:
		del_doc = frappe.qb.DocType("Deleted Document")
		deleted_docs = (
			frappe.qb.from_(del_doc)
			.select(del_doc.deleted_name, del_doc.data)
			.where((del_doc.deleted_doctype == "Asset") & (del_doc.deleted_name.isin(deleted_assets)))
		).run(as_dict=True)

		comp_to_assets = defaultdict(list)
		for doc in deleted_docs:
			try:
				comp_name = frappe.parse_json(doc.data).get("company")
				if comp_name:
					comp_to_assets[comp_name].append(doc.deleted_name)
			except Exception:
				pass

		for comp_name, asset_names in comp_to_assets.items():
			(
				frappe.qb.update(asset_activity)
				.set(asset_activity.company, comp_name)
				.where(asset_activity.asset.isin(asset_names) & missing_company)
			).run()
