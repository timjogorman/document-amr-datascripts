import pathlib
import random
import argparse
import logging

import penman
from penman import DecodeError
from penman.layout import LayoutError

from penman.types import Constant, Variable, Role
from penman.model import Model

from bs4 import BeautifulSoup as bsoup
from amr import model as amrmodel

def get_amr_dict(unsplit_amr3_location):
    '''
    Load a dictionary of all the AMR ids. 
    '''
    amrid2amr = {}
    for each_file in pathlib.Path(unsplit_amr3_location).iterdir():
        for each_amr in each_file.read_text().replace(u'\x85',' ').split("\n\n"):
            if "AMR release" in each_amr:
                continue
            try:
                file = penman.decode(each_amr)
            except DecodeError:
                logging.error("Penman failed to parse an AMR:\n"+str(each_amr))
                print([each_amr])
                continue
            amr_id = file.metadata['id']
            amrid2amr[amr_id] = file
    return amrid2amr

class MSAMRGraph:
    '''
    Class for taking a list of AMRs and MS-AMR information, and producing a single document graph.     
    '''
        
    def __init__(self, name, list_of_amr_ids, amr_dict, clusters, implicits, bridging_links):
        self.list_of_amr_ids =  list_of_amr_ids
        self.amr_dict = amr_dict
        self.clusters = clusters
        self.impl = implicits
        self.bridge_links = bridging_links
        self.DEFAULT_ROOT = 'u99'
        self.name = name

    def rename_with_clusterid(self, variable):
        if variable in self.clusters:
            return self.clusters[variable]
        return variable
    def generate_graph(self, redundancy="redundant"):
        '''
        Genderate document graph
        '''

        all_links = [(self.DEFAULT_ROOT, Role(":instance"),"utterance")] #+ self.bridge_links
        raw_text = []
        for sentence_id, amr in enumerate(self.list_of_amr_ids):
            raw_text.append(self.amr_dict[amr].metadata['snt'])
            all_variables = self.amr_dict[amr].variables()
            top_variable = "s"+str(sentence_id)+self.amr_dict[amr].top
            
            top_variable = self.rename_with_clusterid(top_variable)
            all_links.append((self.DEFAULT_ROOT, Role(":snt"+str(sentence_id+1)),Variable(top_variable)))
            for tr in self.amr_dict[amr].instances():
                source = "s"+str(sentence_id)+str(tr.source)
                impl_stack = []
                if source in self.impl:
                    impl_stack += self.impl[source]

                if str(source) in self.clusters:
                    source = Variable(self.clusters[source])
                all_links.append((source, tr.role, str(tr.target)))
                for mapping in impl_stack:
                    all_links.append((source, Role(":"+str(mapping[0])), mapping[1]))

            for tr in self.amr_dict[amr].attributes():
                source = "s"+str(sentence_id)+str(tr.source)
                if str(source) in self.clusters:
                    source = Variable(self.clusters[source])
                
                all_links.append((source, tr.role, str(tr.target)))

            for tr in self.amr_dict[amr].edges():
                source, role, target = tr.source, tr.role, tr.target
                source = Variable('s'+str(sentence_id)+source)
                target = Variable('s'+str(sentence_id)+target)
                if str(source) in self.clusters:
                    source = Variable(self.clusters[source])
                if str(target) in self.clusters:
                    target = Variable(self.clusters[target])
                    
                tr = (Variable(source), Role(tr.role), target)
                all_links.append(tr)
        all_links += self.bridge_links

        final_links = []
        instance_variables_seen = []
        for triple in all_links:
            is_redundant =False
            if triple in final_links:
                candidate = (triple[0], ":additional-type", triple[2])
                is_redundant =True
            elif triple[1] == ":instance" and triple[0] in instance_variables_seen:
                candidate = (triple[0], ":additional-type", triple[2])
                if candidate in final_links:
                    is_redundant=True
            elif triple[1] == ":instance":
                instance_variables_seen.append(triple[0])
                candidate = triple
            else:
                candidate = triple
            if redundancy == 'unique' and is_redundant:
                pass
            else:
                final_links.append(candidate)
        test = penman.graph.Graph(triples=final_links, top=self.DEFAULT_ROOT)
        test.metadata['snt'] = " ".join(raw_text)
        test.metadata['id'] = self.name
        
        p = penman.encode(test, model=amrmodel)
        return p
        

    @classmethod
    def from_xml(cls, amr_dict, xml_file):

        # get list of amrs


        msamr_obj = bsoup(open(xml_file),'lxml').find('sentences')
        amr2sid = [amr['id'] for amr in msamr_obj.find_all('amr')]

        turns = {}
        ident_chain = []    

        mention2cluster = {}
        impl2cluster = {}
        relation_names = {}
        for mention_type in ['identity','singletons']:
            cluster_iter = bsoup(open(xml_file),'lxml').find(mention_type)
            for chain_id, chain in enumerate(cluster_iter.find_all('identchain')):
                ment_id = "z"+str(len(relation_names))
                relation_names[chain['relationid']] = ment_id

                for mention in chain.find_all("mention"):
                    acode = "s"+str(amr2sid.index(mention["id"]))+mention['variable']
                    mention2cluster[acode] =ment_id

                for implicit in chain.find_all("implicitrole"):
                    parent_code = "s"+str(amr2sid.index(implicit["id"]))+implicit['parentvariable']
                    impl2cluster[parent_code] = impl2cluster.get(parent_code, []) + [(implicit['argument'], ment_id)]
        partial_coref_types = [("setmember","superset","member",":subset"), ("partwhole","whole","part",":part")]
        all_links = []
        for bridging_type, higher_type, lower_type, edge_label in partial_coref_types:
            bridge_iter = bsoup(open(xml_file),'lxml').find("bridging")
            for edge in bridge_iter.find_all(bridging_type):
                rn = relation_names[edge.find(higher_type)['id']]
                for member in edge.find_all(lower_type):
                    tr = (str(rn), edge_label, str(relation_names[member['id']]))
                    if not tr in all_links:
                        all_links.append(tuple(tr))
        return MSAMRGraph(pathlib.Path(xml_file).name, amr2sid, amr_dict, mention2cluster, impl2cluster, all_links)

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Process something like MS-AMR and output one AMR per document')
    parser.add_argument('--amrunsplit',   help='AMR 3.0 data')
    parser.add_argument('--msamr', help='folder of msamr xmls')
    parser.add_argument('--output', help='where to put output graphs')
    commands= parser.parse_args()

    amr_dict = get_amr_dict(commands.amrunsplit)

    for input_file in pathlib.Path(commands.msamr).iterdir():
        print(input_file)
        m = MSAMRGraph.from_xml(amr_dict, input_file)
        whole_graph = m.generate_graph()
        pathlib.Path(commands.output + '/'+ input_file.name+".msamr.txt").write_text(whole_graph)