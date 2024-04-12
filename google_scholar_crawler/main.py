from scholarly import scholarly
import json
import os


def gen_gs_data_by_list(gs_id_list):
    for gs_id in gs_id_list:
        author: dict = scholarly.search_author_id(gs_id)
        os.makedirs('results', exist_ok=True)
        with open(f'results/gs_data_{gs_id}.json', 'w') as outfile:
            json.dump(author, outfile, ensure_ascii=False)

        shieldio_data = {
            "schemaVersion": 1,
            "label": "citations",
            "message": f"{author['citedby']}",
        }

        with open(f'results/gs_data_shieldsio_{gs_id}.json', 'w') as outfile:
            json.dump(shieldio_data, outfile, ensure_ascii=False)


if __name__ == '__main__':
    gs_id_list = (os.environ['GS_ID_LIST']).split(',')
    gen_gs_data_by_list(gs_id_list)
