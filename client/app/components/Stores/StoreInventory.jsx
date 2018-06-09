import React from 'react';
import {Col, Row, Panel, Alert, Table, Glyphicon} from 'react-bootstrap';
import {withRouter, Link} from "react-router-dom";
import {Stomp} from 'stompjs/lib/stomp.min';
import axios from "axios/index";
import _ from "underscore";
import Form from "react-jsonschema-form";

const InventoryItemSchema = {
    type: "object",
    required: ["barcode", "name", "price"],
    properties: {
      barcode: {type: "string", title: "Barcode"},
      name: {type: "string", title: "Name"},
      price: {type: "number", title: "Price"},
      zone: {
          type: "string",
          title: "Zone"
      },
      lsCode: {type: "string", title: "LS Code"}
    }
};

class StoreInventory extends React.Component {
    constructor(props) {
        super(props);
        
        this.state = this.props.editorState ? (this.props.editorState.inventoryState || {}) : {};
    }


    onItemSubmit(submission)
    {
        const newInventoryItem = submission.formData;

        const store = _.clone(this.props.store);
        if (!store.inventory)
        {
            store.inventory = [];
        }

        if (this.state.isEditing)
        {
            const item = _.findWhere(store.inventory, {barcode: newInventoryItem.barcode});
            Object.keys(newInventoryItem).forEach((key) => {item[key] = newInventoryItem[key];});
            this.props.updateStore(store);
            this.setState({isEditing: false});
        }
        else
        {
            // Make sure there isn't already an entry for this barcode
            if (_.findWhere(store.inventory, {barcode: newInventoryItem.barcode}))
            {
                alert("Item with this barcode already exists.");
            }
            else
            {
                store.inventory.push(newInventoryItem);
                this.props.updateStore(store);
            }
        }
    }
    
    setState(newState)
    {
        this.props.updateEditorState({
            inventoryState: newState
        });
    }

    onEditItemClick(item, event)
    {
        this.setState({
            editItem: item,
            isEditing: true
        });
    }

    onDeleteItemClick(deleteItem, event)
    {
        const store = _.clone(this.props.store);
        store.inventory = _.filter(store.inventory, (item) =>(item.barcode !== deleteItem.barcode));
        this.props.updateStore(store);

    }


    render() {
        const storeInventorySchema = _.clone(InventoryItemSchema);
        storeInventorySchema.properties.zone.enum = this.props.store.zones.map((zone) => (zone.id).toString());

        return (
            <div className="store-inventory">
                <br/>
                <Row><Glyphicon glyph="align-left" />
                    <Col md={8}>
                        <Table striped bordered condensed hover>
                            <thead>
                                <tr>
                                    <th>SKU Number</th>
                                    <th>Name</th>
                                    <th>Price</th>
                                    <th>Zone</th>
                                    <th>LS Code</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                            {
                                (this.props.store.inventory) ?
                                    this.props.store.inventory.map((item) =>
                                    {
                                        return <tr key={item.barcode}>
                                            <td>{item.barcode}</td>
                                            <td>{item.name}</td>
                                            <td>{item.price}</td>
                                            <td>{item.zone}</td>
                                            <td>{item.lsCode}</td>
                                            <td>
                                                <i className={"fa fa-edit"} onClick={this.onEditItemClick.bind(this, item)} />
                                                <i className={"fa fa-times"} onClick={this.onDeleteItemClick.bind(this, item)} />
                                            </td>
                                        </tr>
                                    })
                                    : null
                            }
                            </tbody>
                        </Table>
                    </Col>
                    <Col md={4}>
                        {
                            this.state.isEditing
                            ? <h1>Editing Item</h1>
                            : <h1>New Item</h1>
                        }
                        <Form schema={storeInventorySchema}
                              onSubmit={this.onItemSubmit.bind(this)}
                              formData={this.state.editItem}
                        />
                    </Col>
                </Row>
            </div>
        );
    }
}

export default withRouter(StoreInventory);


